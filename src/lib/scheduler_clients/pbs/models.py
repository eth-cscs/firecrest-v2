# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import Optional
from datetime import datetime
import re

from pydantic import AliasChoices, Field, field_validator

# models
from lib.scheduler_clients.models import (
    JobDescriptionModel,
    JobMetadataModel,
    JobModel,
    JobStatus,
    JobTime,
    NodeModel,
    PartitionModel,
    ReservationModel,
    SchedPing,
)


class PbsJobDescription(JobDescriptionModel):
    pass


class PbsJobMetadata(JobMetadataModel):
    standard_output: Optional[str] = Field(
        validation_alias=AliasChoices("Error_Path"), default=None
    )
    standard_error: Optional[str] = Field(
        validation_alias=AliasChoices("Output_Path"), default=None
    )

    @field_validator("standard_output", "standard_error", mode="before")
    @classmethod
    def _parse_pbs_path(cls, v):
        """
        Removes the cluster name and the colon from the start of a PBS path,
         e.g. "pbs:/home/fireuser/test_dir/hello_pbs.o1" into
        "/home/fireuser/test_dir/hello_pbs.o1"
        """
        return re.sub(r"^[^:]+:", "", v)


class JobStatusPbs(JobStatus):
    pass


class JobTimePbs(JobTime):
    end: None = None
    suspended: None = None

    @field_validator("elapsed", "limit", mode="before")
    @classmethod
    def _parse_duration(cls, v):
        """
        Turn "HH:MM:SS" into total seconds.
        If it's already an int (or None), just pass it through.
        """
        if isinstance(v, str):
            try:
                h, m, s = map(int, v.split(":"))
                return h * 3600 + m * 60 + s
            except ValueError:
                raise ValueError(f"invalid duration string: {v!r}") from None
        return v

    @field_validator("start", mode="before")
    @classmethod
    def _parse_timestamp(cls, v):
        """
        Turn "Wed May 14 11:52:02 2025" into a UNIX timestamp (int).
        If it's already an int (or None), just pass it through.
        """
        if isinstance(v, str):
            dt = datetime.strptime(v, "%a %b %d %H:%M:%S %Y")
            return int(dt.timestamp())
        return v


class PbsJob(JobModel):
    name: str = Field(alias=AliasChoices("Job_Name"))
    status: JobStatusPbs
    time: JobTimePbs
    account: str = Field(alias=AliasChoices("project"))
    nodes: str = Field(alias=AliasChoices("exec_host"))
    partition: str = Field(alias=AliasChoices("queue"))
    priority: int = Field(alias=AliasChoices("Priority"))

    def __init__(self, **kwargs):
        kwargs["working_directory"] = kwargs.get("Variable_List", {}).get(
            "PBS_O_WORKDIR", None
        )
        kwargs["nodes"] = kwargs.get("Resource_List", {}).get("nodes", None)
        kwargs["cluster"] = kwargs.get("Job_Owner", "").split("@")[1]
        kwargs["allocation_nodes"] = kwargs.get("Resource_List", {}).get("nodect", None)

        times = {}
        times["elapsed"] = kwargs.get("resources_used", {}).get("walltime", None)
        times["start"] = kwargs.get("stime", None)
        times["limit"] = kwargs.get("Resource_List", {}).get("walltime", None)
        kwargs["time"] = JobTimePbs(**times)

        status = {}
        status["state"] = kwargs.get("job_state", "")
        status["exitCode"] = int(kwargs.get("Exit_status", 0))
        kwargs["status"] = JobStatusPbs(**status)
        super().__init__(**kwargs)

    @field_validator("nodes", mode="before")
    @classmethod
    def _parse_nodelist(cls, v):
        nodes = []
        for chunk in v.split("+"):
            host = chunk.split("/")[0]  # drop the “/0”
            m = re.match(r"([^\[]+)\[(\d+)-(\d+)\]", host)
            if m:
                prefix, start, end = m.groups()
                width = len(start)
                for i in range(int(start), int(end) + 1):
                    nodes.append(f"{prefix}{i:0{width}d}")
            else:
                nodes.append(host)
        return ",".join(nodes)


class PbsNode(NodeModel):
    pass


class PbsPing(SchedPing):
    pass


class PbsPartition(PartitionModel):
    pass


class PbsReservation(ReservationModel):
    start_time: Optional[str] = Field(
        default=None, alias=AliasChoices("startTime", "start_time")
    )
    end_time: Optional[str] = Field(
        default=None, alias=AliasChoices("endTime", "end_time")
    )

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _parse_timestamp(cls, v):
        """
        Turn "Wed May 14 11:52:02 2025" into a UNIX timestamp (int).
        If it's already an int (or None), just pass it through.
        """
        if isinstance(v, str):
            dt = datetime.strptime(v, "%a %b %d %H:%M:%S %Y")
            return int(dt.timestamp())
        return v
