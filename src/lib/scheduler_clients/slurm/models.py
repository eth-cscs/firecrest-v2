# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import (
    AliasChoices,
    Field,
    field_validator,
    model_validator,
)

# models
from lib.scheduler_clients.models import (
    AccountsModel,
    JobDescriptionModel,
    JobMetadataModel,
    JobModel,
    JobStatus,
    JobTask,
    JobTime,
    NodeModel,
    NodeState,
    PartitionModel,
    ReservationModel,
    SchedPing,
)

_SLURM_STATE_MAP: dict[str, NodeState] = {
    "idle": NodeState.IDLE,
    "allocated": NodeState.ALLOCATED,
    "alloc": NodeState.ALLOCATED,
    "mixed": NodeState.MIXED,
    "mix": NodeState.MIXED,
    "down": NodeState.DOWN,
    "fail": NodeState.DOWN,
    "failing": NodeState.DOWN,
    "failg": NodeState.DOWN,
    "drain": NodeState.DRAIN,
    "drained": NodeState.DRAIN,
    "draining": NodeState.DRAIN,
    "drng": NodeState.DRAIN,
    "completing": NodeState.COMPLETING,
    "comp": NodeState.COMPLETING,
    "maint": NodeState.OFFLINE,
    "reserved": NodeState.RESERVED,
    "resv": NodeState.RESERVED,
    "power_down": NodeState.POWERING_DOWN,
    "pow_dn": NodeState.POWERING_DOWN,
    "power_up": NodeState.POWERING_UP,
    "pow_up": NodeState.POWERING_UP,
    "future": NodeState.UNKNOWN,
    "futr": NodeState.UNKNOWN,
    "planned": NodeState.UNKNOWN,
    "plnd": NodeState.UNKNOWN,
    "blocked": NodeState.UNKNOWN,
    "unknown": NodeState.UNKNOWN,
    "unk": NodeState.UNKNOWN,
    "perfctrs": NodeState.UNKNOWN,
    "npc": NodeState.UNKNOWN,
}


def _map_slurm_state(raw: str) -> NodeState:
    # Strip sinfo suffix flags (*, +, ~, #, %, $, @) and normalize case
    key = raw.rstrip("*+~#%$@").lower()
    return _SLURM_STATE_MAP.get(key, NodeState.UNKNOWN)


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
    job_id: str = Field(
        validation_alias=AliasChoices("JobId", "jobId", "job_id"),
    )
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

    def __init__(self, **kwargs):
        # Accounting reports CPU time as time.total {seconds, microseconds}
        if "total_cpu" not in kwargs and isinstance(kwargs.get("total"), dict):
            kwargs["total_cpu"] = kwargs["total"].get("seconds")
        super().__init__(**kwargs)

    @field_validator(
        "elapsed", "start", "end", "suspended", "limit", "submission", mode="before"
    )
    @classmethod
    def _parse_time(cls, v):
        return slurm_int_to_int(v)


def _tres_count(tres_list, tres_type: str) -> Optional[int]:
    for tres in tres_list or []:
        if tres.get("type") == tres_type and not tres.get("name"):
            return tres.get("count")
    return None


def _named_tres_count(tres_list, tres_type: str, name: str) -> Optional[int]:
    for tres in tres_list or []:
        if tres.get("type") == tres_type and tres.get("name") == name:
            return tres.get("count")
    return None


def _step_peak(steps, kind: str, tres_type: str, name: str = "") -> Optional[int]:
    """Largest value of a step usage TRES (tres.requested.<kind>) over the steps."""
    values = [
        _named_tres_count(
            ((step.get("tres") or {}).get("requested") or {}).get(kind), tres_type, name
        )
        for step in steps or []
    ]
    values = [v for v in values if v is not None]
    return max(values) if values else None


def _max_rss(steps) -> Optional[int]:
    """Largest step peak RSS (bytes): sacct's MaxRSS for the job."""
    return _step_peak(steps, "max", "mem")


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
                nodes = kwargs["job_resources"]["nodes"]
                if isinstance(nodes, dict):
                    kwargs["allocation_nodes"] = nodes.get("count", 0)
                else:
                    kwargs["allocation_nodes"] = kwargs["job_resources"].get("allocated_hosts", 0)
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
                    submission=slurm_int_to_int(kwargs.get("submit_time")),
                )

        # Resources: accounting has TRES lists, the controller plain counts
        tres = kwargs.get("tres") or {}
        if "allocation_cpus" not in kwargs:
            cpus = _tres_count(tres.get("allocated"), "cpu")
            if cpus is None and "cpus" in kwargs:
                cpus = slurm_int_to_int(kwargs["cpus"])
            kwargs["allocation_cpus"] = cpus or None
        if "requested_memory" not in kwargs:
            memory = _tres_count(tres.get("requested"), "mem")
            if memory is None and "memory_per_node" in kwargs:
                per_node = slurm_int_to_int(kwargs["memory_per_node"])
                if per_node:
                    memory = per_node * max(kwargs.get("allocation_nodes") or 1, 1)
            kwargs["requested_memory"] = memory or None
        if "max_rss" not in kwargs and isinstance(kwargs.get("steps"), list):
            kwargs["max_rss"] = _max_rss(kwargs["steps"])
        if "allocation_gpus" not in kwargs:
            kwargs["allocation_gpus"] = (
                _named_tres_count(tres.get("allocated"), "gres", "gpu") or None
            )
        if "consumed_energy" not in kwargs:
            kwargs["consumed_energy"] = _tres_count(tres.get("allocated"), "energy") or None
        if isinstance(kwargs.get("steps"), list):
            # What the NVML gpu plugin samples (gres/gpuutil, gres/gpumem)
            kwargs.setdefault(
                "gpu_utilization", _step_peak(kwargs["steps"], "average", "gres", "gpuutil")
            )
            kwargs.setdefault(
                "max_gpu_memory", _step_peak(kwargs["steps"], "max", "gres", "gpumem")
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
    def __init__(self, **kwargs):
        if "state" in kwargs:
            state = kwargs.get("state", [])
            kwargs["state"] = [_map_slurm_state(s) for s in state]
        # slurmrestd names: free_mem (MiB, NO_VAL struct), alloc_idle_cpus,
        # cpu_load (load average x 100)
        if "free_memory" not in kwargs and "free_mem" in kwargs:
            kwargs["free_memory"] = slurm_int_to_int(kwargs["free_mem"])
        if "idle_cpus" not in kwargs and "alloc_idle_cpus" in kwargs:
            kwargs["idle_cpus"] = kwargs["alloc_idle_cpus"]
        if isinstance(kwargs.get("cpu_load"), dict):
            kwargs["cpu_load"] = slurm_int_to_int(kwargs["cpu_load"])
        if isinstance(kwargs.get("partitions"), str):
            kwargs["partitions"] = kwargs["partitions"].split(",")
        super().__init__(**kwargs)


class SlurmPing(SchedPing):
    pass


class SlurmAccounts(AccountsModel):
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
    features: Optional[str] = Field(
        validation_alias=AliasChoices("features", "Features"),
        default=None,
        nullable=True,
    )
    state: Optional[str] = Field(
        validation_alias=AliasChoices("state", "State"), default=None, nullable=True
    )

    @field_validator("node_count", mode="before")
    @classmethod
    def _parse_count(cls, v):
        return slurm_int_to_int(v)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _parse_time(cls, v):
        return slurm_int_to_int(v)

    @model_validator(mode="after")
    def set_state(self):
        if self.state is None:
            now = int(datetime.now(timezone.utc).timestamp())
            if self.start_time <= now < self.end_time:
                self.state = "active"
            else:
                self.state = "inactive"
        elif not self.state.islower():
            self.state = self.state.lower()
        return self
