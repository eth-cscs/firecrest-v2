# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import Optional
from datetime import datetime, timezone
import re

from pydantic import AliasChoices, Field, field_validator

# models
from lib.scheduler_clients.models import (
    AccountsModel,
    JobDescriptionModel,
    JobMetadataModel,
    JobModel,
    JobStatus,
    JobTime,
    NodeModel,
    NodeState,
    PartitionModel,
    ReservationModel,
    SchedPing,
)

_PBS_STATE_MAP: dict[str, NodeState] = {
    "free": NodeState.IDLE,
    "job-exclusive": NodeState.ALLOCATED,
    "job-sharing": NodeState.MIXED,
    "time-shared": NodeState.MIXED,
    "down": NodeState.DOWN,
    "offline": NodeState.OFFLINE,
    "reserve": NodeState.RESERVED,
    "busy": NodeState.BUSY,
    "state-unknown": NodeState.UNKNOWN,
}


def _map_pbs_state(raw: str) -> NodeState:
    return _PBS_STATE_MAP.get(raw.lower(), NodeState.UNKNOWN)


def parse_timestamp(value):
    """
    Turn "Wed May 14 11:52:02 2025" into a UNIX timestamp (int).
    The PBS commands are run with TZ=UTC, so the time is read as UTC.
    If it's already an int (or None), just pass it through.
    """
    if isinstance(value, str):
        dt = datetime.strptime(value, "%a %b %d %H:%M:%S %Y")
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    return value


_SIZE_SHIFT = {"": 0, "k": 10, "m": 20, "g": 30, "t": 40, "p": 50}
# PBS words are 8 bytes (SIZEOF_WORD in OpenPBS)
_SIZE_UNIT = {"": 1, "b": 1, "w": 8}


def parse_size(value):
    """
    Turn a PBS size like "5660kb" into bytes. PBS multipliers are binary
    and a bare number is in bytes. Unrecognised strings give None, while
    ints (or None) are passed through.
    """
    if isinstance(value, str):
        m = re.fullmatch(r"(\d+)([kmgtp]?)([bw]?)", value.strip().lower())
        if m is None:
            return None
        number, multiplier, unit = m.groups()
        return (int(number) << _SIZE_SHIFT[multiplier]) * _SIZE_UNIT[unit]
    return value


class PbsJobDescription(JobDescriptionModel):
    pass


class PbsJobMetadata(JobMetadataModel):
    standard_output: Optional[str] = Field(
        validation_alias=AliasChoices("Error_Path"), default=None, nullable=True
    )
    standard_error: Optional[str] = Field(
        validation_alias=AliasChoices("Output_Path"), default=None, nullable=True
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

    @field_validator("elapsed", "limit", "total_cpu", mode="before")
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

    @field_validator("start", "submission", mode="before")
    @classmethod
    def _parse_timestamp(cls, v):
        return parse_timestamp(v)


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
        times["submission"] = kwargs.get("ctime", None)
        times["total_cpu"] = kwargs.get("resources_used", {}).get("cput", None)
        kwargs["time"] = JobTimePbs(**times)

        kwargs["allocation_cpus"] = kwargs.get("Resource_List", {}).get("ncpus", None)
        memory = parse_size(kwargs.get("Resource_List", {}).get("mem", None))
        kwargs["requested_memory"] = memory >> 20 if memory else None
        kwargs["max_rss"] = parse_size(
            kwargs.get("resources_used", {}).get("mem", None)
        )
        # ngpus is not built into PBS, but it is the name sites define for GPUs
        kwargs["allocation_gpus"] = kwargs.get("Resource_List", {}).get("ngpus", None)
        # Set by PBS power hooks, in kWh
        energy = kwargs.get("resources_used", {}).get("energy", None)
        kwargs["consumed_energy"] = (
            round(float(energy) * 3_600_000) if energy is not None else None
        )

        status = {}
        status["state"] = kwargs.get("job_state", "")
        status["exitCode"] = int(kwargs.get("Exit_status", 0))
        kwargs["status"] = JobStatusPbs(**status)
        super().__init__(**kwargs)

    @field_validator("nodes", mode="before")
    @classmethod
    def _parse_nodelist(cls, v):
        if v is None or v == "":
            # This string has been chosen to keep compatibility with the
            # Slurm scheduler.
            return "None assigned"

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

    @field_validator("account", mode="before")
    @classmethod
    def cast_account_to_str(cls, v):
        return str(v)


class PbsNode(NodeModel):
    cpus: int = Field(alias=AliasChoices("pcpus"))

    def __init__(self, **kwargs):

        kwargs["idle_cpus"] = kwargs.get("resources_available", {}).get("ncpus", 0)
        kwargs["free_memory"] = kwargs.get("resources_available", {}).get("mem", None)
        kwargs["hostname"] = kwargs.get("resources_available", {}).get("host", None)
        kwargs["alloc_memory"] = kwargs.get("resources_assigned", {}).get("mem", None)
        kwargs["alloc_cpus"] = kwargs.get("resources_assigned", {}).get("ncpus", 0)
        # e.g. set with pbsnodes -o -C, or by the server when a node goes down
        kwargs["reason"] = kwargs.get("comment", None)
        state = kwargs.get("state", [])
        if isinstance(state, str):
            state = [state]
        kwargs["state"] = [_map_pbs_state(s) for s in state]

        super().__init__(**kwargs)

    @field_validator("free_memory", "alloc_memory", mode="before")
    @classmethod
    def _parse_memory(cls, value):
        """
        Convert memory from a string like "16gb" to MiB, as Slurm reports it.
        """
        if isinstance(value, str):
            memory = parse_size(value)
            return memory >> 20 if memory is not None else None

        return value


class PbsPing(SchedPing):
    pass


class PbsAccounts(AccountsModel):
    pass


class PbsPartition(PartitionModel):
    partition: str = Field(alias=AliasChoices("started"))

    @field_validator("partition", mode="before")
    @classmethod
    def _parse_state(cls, v):
        # Not sure if we should use both "started" and "enabled" attributes
        state = "UP" if v.lower() == "true" else "DOWN"
        return state


class PbsReservation(ReservationModel):

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _parse_timestamp(cls, v):
        return parse_timestamp(v)
