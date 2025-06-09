# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# models
from typing import Dict, List, Optional, Any
from lib.models.base_model import CamelModel
from pydantic import AliasChoices, Field, RootModel, validator
import re
from datetime import datetime


class CustomInt(RootModel):
    root: int | None

    # starting from v0.0.40 slurm api represents int with a complex object
    # e.s. {"set": True, "infinite": False, "number": 0},
    def __init__(self, **kwargs):
        if kwargs["set"] == "False":
            super().__init__(None)
        else:
            super().__init__(kwargs["number"])


class Partition(RootModel):
    root: List[str]

    def __init__(self, **kwargs):
        super().__init__(kwargs["state"])


class PartitionCPUs(RootModel):
    root: int

    def __init__(self, **kwargs):
        super().__init__(kwargs["total"])


class JobStatus(CamelModel):
    state: str
    stateReason: Optional[str] = None
    exitCode: CustomInt
    interruptSignal: Optional[CustomInt] = None

    def __init__(self, **kwargs):
        if isinstance(kwargs["state"], list):
            if len(kwargs["state"]) > 0:
                kwargs["state"] = kwargs["state"][0]
            else:
                kwargs["state"] = None

        super().__init__(**kwargs)


class JobTime(CamelModel):
    elapsed: Optional[CustomInt] = None
    start: Optional[CustomInt] = None
    end: Optional[CustomInt] = None
    suspended: Optional[CustomInt] = None
    limit: Optional[CustomInt] = None

    @validator("elapsed", "limit", pre=True)
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

    @validator("start", pre=True)
    def _parse_timestamp(cls, v):
        """
        Turn "Wed May 14 11:52:02 2025" into a UNIX timestamp (int).
        If it's already an int (or None), just pass it through.
        """
        if isinstance(v, str):
            dt = datetime.strptime(v, "%a %b %d %H:%M:%S %Y")
            return int(dt.timestamp())
        return v


class JobTask(CamelModel):
    id: str
    name: str
    status: JobStatus
    time: JobTime

    def __init__(self, **kwargs):
        # Custom task field definition
        if "step" in kwargs:
            kwargs["id"] = kwargs["step"]["id"]
            kwargs["name"] = kwargs["step"]["name"]

        if "exit_code" in kwargs:
            interruptSignal = None
            if "signal" in kwargs["exit_code"]:
                interruptSignal = kwargs["exit_code"]["signal"]["id"]

            kwargs["status"] = {
                "state": kwargs["state"],
                "stateReason": None,
                "exitCode": kwargs["exit_code"]["return_code"],
                "interruptSignal": interruptSignal,
            }
        super().__init__(**kwargs)


class JobModel(CamelModel):

    def __init__(self, **kwargs):
        # Custom status field definition
        if "exit_code" in kwargs:
            interruptSignal = None
            if "signal" in kwargs["exit_code"]:
                interruptSignal = kwargs["exit_code"]["signal"]["id"]

            kwargs["status"] = {
                "state": kwargs["state"]["current"],
                "stateReason": kwargs["state"]["reason"],
                "exitCode": kwargs["exit_code"]["return_code"],
                "interruptSignal": interruptSignal,
            }
        if "steps" in kwargs:
            kwargs["tasks"] = kwargs["steps"]
        super().__init__(**kwargs)

    job_id: int
    name: str
    status: JobStatus
    tasks: Optional[List[JobTask]] = None
    time: JobTime
    account: Optional[str]
    allocation_nodes: int
    cluster: str
    group: Optional[str] = None
    nodes: str
    partition: str
    priority: CustomInt
    kill_request_user: Optional[str] = None
    user: Optional[str]
    working_directory: str


class JobMetadataModel(CamelModel):
    job_id: int
    script: Optional[str] = None
    standard_input: Optional[str] = Field(
        validation_alias=AliasChoices("StdIn", "standardInput"), default=None
    )
    standard_output: Optional[str] = Field(
        validation_alias=AliasChoices("StdOut", "standardOutput"), default=None
    )
    standard_error: Optional[str] = Field(
        validation_alias=AliasChoices("StdErr", "standardError"), default=None
    )


class JobDescriptionModel(CamelModel):
    name: Optional[str] = Field(default=None, description="Name for the job")
    account: Optional[str] = Field(
        default=None, description="Charge job resources to specified account"
    )
    current_working_directory: str = Field(
        alias="working_directory", description="Job working directory"
    )
    standard_input: Optional[str] = Field(
        default=None, description="Standard input file name"
    )
    standard_output: Optional[str] = Field(
        default=None, description="Standard output file name"
    )
    standard_error: Optional[str] = Field(
        default=None, description="Standard error file name"
    )
    environment: Optional[Dict[str, str] | List[str]] = Field(
        alias="env",
        default={"F7T_version": "v2.0.0"},
        description="Dictionary of environment variables to set in the job context",
    )
    constraints: Optional[str] = Field(default=None, description="Job constraints")
    script: str = Field(default=None, description="Script for the job")
    script_path: str = Field(
        default=None, description="Path to the job in target system"
    )


class JobSubmitRequestModel(CamelModel):
    pass


class NodeModel(CamelModel):
    sockets: Optional[int] = None
    cores: Optional[int] = None
    threads: Optional[int] = None
    cpus: Optional[int] = None
    cpu_load: Optional[float] = None
    free_memory: Optional[int] = None
    memory: Optional[str] = None
    features: Optional[str | List[str]] = None
    name: str
    address: Optional[str] = None
    hostname: Optional[str] = None
    state: str | List[str]  # e.g. ["IDLE", "RESERVED"]
    partitions: Optional[List[str]] = None
    weight: Optional[int] = None
    slurmd_version: Optional[str] = None
    alloc_memory: Optional[int] = None
    alloc_cpus: Optional[int] = None
    idle_cpus: Optional[int] = None


class SchedulerPing(CamelModel):
    hostname: Optional[str] = None
    pinged: Optional[str] = None
    latency: Optional[int] = None
    mode: Optional[str] = None


class Partition(RootModel):
    root: List[str]

    def __init__(self, **kwargs):
        super().__init__(kwargs["state"])


class ReservationModel(CamelModel):
    name: str = Field(
        validation_alias=AliasChoices("reservationName", "ReservationName")
    )
    node_list: str = Field(validation_alias=AliasChoices("nodes", "Nodes", "nodeList"))
    end_time: int | CustomInt = Field(
        validation_alias=AliasChoices("endTime", "EndTime")
    )
    start_time: int | CustomInt = Field(
        validation_alias=AliasChoices("startTime", "StartTime")
    )
    features: Optional[str] = Field(validation_alias=AliasChoices("Features"))


class PartitionModel(CamelModel):
    name: str = Field(validation_alias=AliasChoices("partitionName", "PartitionName"))
    cpus: int | PartitionCPUs = Field(
        validation_alias=AliasChoices("totalCPUs", "total_cpus", "TotalCPUs")
    )
    total_nodes: int = Field(validation_alias=AliasChoices("totalNodes", "TotalNodes"))
    partition: Partition | str = Field(validation_alias=AliasChoices("state", "State"))

    def __init__(self, **kwargs):

        # To allow back compatibility with Slurm API versions <= 0.0.38
        if "total_nodes" not in kwargs and "nodes" in kwargs:
            kwargs["total_nodes"] = kwargs["nodes"]["total"]
        super().__init__(**kwargs)
