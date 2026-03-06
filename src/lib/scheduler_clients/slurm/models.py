# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import List, Optional

from pydantic import (
    AliasChoices,
    Field,
    field_validator,
)

# models
from lib.scheduler_clients.models import (
    JobDescriptionModel,
    JobMetadataModel,
    JobModel,
    JobStatus,
    JobTask,
    JobTime,
    NodeModel,
    PartitionModel,
    ReservationModel,
    SchedPing,
)


def slurm_int_to_int(v) -> Optional[int]:
    # starting from v0.0.40 slurm api represents int with a complex object
    # e.s. {"set": True, "infinite": False, "number": 0},
    if v is None or isinstance(v, int) or isinstance(v, float):
        return v

    if isinstance(v, str):
        try:
            # FIXME: not sure if this is always int or can be float
            return int(v)
        except ValueError:
            raise ValueError(f"Invalid SlurmInt value: {v!r}") from None

    if isinstance(v, dict):
        if not v.get("set", True):
            return None

        return int(v.get("number"))


class SlurmJobDescription(JobDescriptionModel):
    pass


class SlurmJobMetadata(JobMetadataModel):
    standard_input: Optional[str] = Field(
        validation_alias=AliasChoices("StdIn", "standardInput"),
        default=None,
        nullable=True,
    )
    standard_output: Optional[str] = Field(
        validation_alias=AliasChoices("StdOut", "standardOutput"),
        default=None,
        nullable=True,
    )
    standard_error: Optional[str] = Field(
        validation_alias=AliasChoices("StdErr", "standardError"),
        default=None,
        nullable=True,
    )


class JobStatusSlurm(JobStatus):
    def __init__(self, **kwargs):
        if isinstance(kwargs["state"], list):
            if len(kwargs["state"]) > 0:
                kwargs["state"] = kwargs["state"][0]
            else:
                kwargs["state"] = None

        super().__init__(**kwargs)

    @field_validator("exitCode", "interruptSignal", mode="before")
    @classmethod
    def _parse_time(cls, v):
        return slurm_int_to_int(v)


class JobTimeSlurm(JobTime):

    @field_validator("elapsed", "start", "end", "suspended", "limit", mode="before")
    @classmethod
    def _parse_time(cls, v):
        return slurm_int_to_int(v)


class JobTaskSlurm(JobTask):

    time: JobTimeSlurm

    def __init__(self, **kwargs):
        # Custom task field definition
        if "step" in kwargs:
            kwargs["id"] = kwargs["step"]["id"]
            kwargs["name"] = kwargs["step"]["name"]

        if "exit_code" in kwargs:
            interruptSignal = None
            exitCode = None

            if kwargs["exit_code"] and "return_code" in kwargs["exit_code"]:
                exitCode = kwargs["exit_code"]["return_code"]

            if kwargs["exit_code"] and "signal" in kwargs["exit_code"]:
                interruptSignal = kwargs["exit_code"]["signal"]["id"]

            kwargs["status"] = JobStatusSlurm(
                state=kwargs["state"],
                stateReason=None,
                exitCode=exitCode,
                interruptSignal=interruptSignal,
            )

        super().__init__(**kwargs)


class SlurmJob(JobModel):

    user: Optional[str] = Field(
        validation_alias=AliasChoices("user_name", "userName"),
        default=None,
        nullable=True,
    )
    working_directory: str = Field(
        validation_alias=AliasChoices(
            "current_working_directory", "workingDirectory", "currentWorkingDirectory"
        )
    )
    allocation_nodes: int

    tasks: Optional[List[JobTaskSlurm]] = Field(
        validation_alias=AliasChoices("steps"), default=None, nullable=True
    )
    time: JobTimeSlurm

    def __init__(self, **kwargs):
        # Remove task field
        if "tasks" in kwargs:
            kwargs["tasks"] = None

        # Custom nodes count extraction
        if "allocation_nodes" not in kwargs and "job_resources" in kwargs:
            if kwargs["job_resources"] and "nodes" in kwargs["job_resources"]:
                kwargs["allocation_nodes"] = kwargs["job_resources"]["nodes"]["count"]
            else:
                kwargs["allocation_nodes"] = 0

        # Custom time field definition
        if "time" not in kwargs and "start_time" in kwargs and "end_time" in kwargs:
            start = slurm_int_to_int(kwargs["start_time"])
            end = slurm_int_to_int(kwargs["end_time"])
            limit = slurm_int_to_int(kwargs["time_limit"])
            suspend_time = slurm_int_to_int(kwargs["suspend_time"])

            if start is not None and end is not None:
                kwargs["time"] = JobTimeSlurm(
                    elapsed=None,
                    start=start,
                    end=end,
                    suspended=suspend_time,
                    limit=limit,
                )

        # Custom status field definition
        if "exit_code" in kwargs:
            interruptSignal = None
            exitCode = None

            if kwargs["exit_code"] and "return_code" in kwargs["exit_code"]:
                exitCode = kwargs["exit_code"]["return_code"]

            if kwargs["exit_code"] and "signal" in kwargs["exit_code"]:
                interruptSignal = kwargs["exit_code"]["signal"]["id"]

            kwargs["status"] = JobStatusSlurm(
                state=(
                    kwargs["job_state"]
                    if "job_state" in kwargs
                    else kwargs["state"]["current"]
                ),
                stateReason=(
                    kwargs["state_reason"]
                    if "state_reason" in kwargs
                    else kwargs["state"]["reason"]
                ),
                exitCode=exitCode,
                interruptSignal=interruptSignal,
            )

        super().__init__(**kwargs)

    @field_validator("priority", mode="before")
    @classmethod
    def _parse_int(cls, v):
        return slurm_int_to_int(v)

    @field_validator("job_id", mode="before")
    @classmethod
    def cast_slurm_jobid_to_str(cls, v):
        return str(v)


class SlurmNode(NodeModel):
    pass


class SlurmPing(SchedPing):
    pass


class SlurmPartitions(PartitionModel):
    name: str = Field(validation_alias=AliasChoices("partitionName", "PartitionName"))
    cpus: int = Field(
        validation_alias=AliasChoices("totalCPUs", "total_cpus", "TotalCPUs")
    )
    total_nodes: int = Field(validation_alias=AliasChoices("totalNodes", "TotalNodes"))
    partition: str | List[str] = Field(validation_alias=AliasChoices("state", "State"))

    def __init__(self, **kwargs):

        # To allow back compatibility with Slurm API versions <= 0.0.38
        if "total_nodes" not in kwargs and "nodes" in kwargs:
            kwargs["total_nodes"] = kwargs["nodes"]["total"]

        if "cpus" in kwargs and isinstance(kwargs["cpus"], dict):
            kwargs["cpus"] = kwargs["cpus"]["total"]

        if "partition" in kwargs and isinstance(kwargs["partition"], dict):
            kwargs["partition"] = kwargs["partition"]["state"]

        super().__init__(**kwargs)


class SlurmReservations(ReservationModel):
    name: str = Field(
        validation_alias=AliasChoices("reservationName", "ReservationName")
    )
    node_list: str = Field(validation_alias=AliasChoices("nodes", "Nodes", "nodeList"))
    end_time: int = Field(validation_alias=AliasChoices("endTime", "EndTime"))
    start_time: int = Field(validation_alias=AliasChoices("startTime", "StartTime"))
    features: Optional[str] = Field(validation_alias=AliasChoices("Features"))

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _parse_time(cls, v):
        return slurm_int_to_int(v)
