# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import Dict, List, Optional

from pydantic import AliasChoices, Field, RootModel

# models
from lib.models.base_model import CamelModel
from lib.scheduler_clients.models import (
    JobMetadataModel,
    JobModel,
    JobDescriptionModel,
    JobStatus,
    JobTask,
    JobTime,
    NodeModel,
    PartitionModel,
    ReservationModel,
)


class SlurmInt(RootModel):
    root: int | None

    # starting from v0.0.40 slurm api represents int with a complex object
    # e.s. {"set": True, "infinite": False, "number": 0},
    def __init__(self, **kwargs):
        if kwargs["set"] == "False":
            super().__init__(None)
        else:
            super().__init__(kwargs["number"])


class SlurmJobDescription(JobDescriptionModel):
    name: Optional[str] = Field(default=None, description="Name for the job")
    current_working_directory: str = Field(alias="working_directory", description="Job working directory")
    standard_input: Optional[str] = Field(default=None, description="Standard input file name")
    standard_output: Optional[str] = Field(default=None, description="Standard output file name")
    standard_error: Optional[str] = Field(default=None, description="Standard error file name")
    environment: Optional[Dict[str, str] | List[str]] = Field(
        alias="env", default={"F7T_version": "v2.0.0"}, description="Dictionary of environment variables to set in the job context"
    )
    constraints: Optional[str] = Field(default=None, description="Job constraints")
    script: str = Field(description="Script for the job")


class SlurmJobMetadata(JobMetadataModel):
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


class JobStatusSlurm(JobStatus):
    state: str
    stateReason: Optional[str] = None
    exitCode: SlurmInt
    interruptSignal: Optional[SlurmInt] = None

    def __init__(self, **kwargs):
        if isinstance(kwargs["state"], list):
            if len(kwargs["state"]) > 0:
                kwargs["state"] = kwargs["state"][0]
            else:
                kwargs["state"] = None

        super().__init__(**kwargs)


class JobTimeSlurm(JobTime):
    elapsed: Optional[SlurmInt]
    start: Optional[SlurmInt]
    end: Optional[SlurmInt]
    suspended: Optional[SlurmInt]
    limit: Optional[SlurmInt] = None


class JobTaskSlurm(JobTask):
    id: str
    name: str
    status: JobStatusSlurm
    time: JobTimeSlurm

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


class SlurmJob(JobModel):

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

    status: JobStatusSlurm
    tasks: Optional[List[JobTaskSlurm]] = None
    time: JobTimeSlurm
    account: Optional[str]
    allocation_nodes: int
    cluster: str
    group: str
    nodes: str
    partition: str
    priority: SlurmInt
    kill_request_user: Optional[str] = None
    user: Optional[str]
    working_directory: str


class SlurmNode(NodeModel):
    sockets: int
    cores: int
    threads: int
    cpus: int
    cpu_load: Optional[float] = None
    free_memory: Optional[int] = None
    features: str | List[str]
    name: str
    address: str
    hostname: str
    state: str | List[str]  # e.g. ["IDLE", "RESERVED"]
    partitions: List[str]
    weight: int
    slurmd_version: Optional[str] = None
    alloc_memory: Optional[int] = None
    alloc_cpus: Optional[int] = None
    idle_cpus: Optional[int] = None


class SlurmPing(CamelModel):
    hostname: Optional[str] = None
    pinged: Optional[str] = None
    latency: Optional[int] = None
    mode: Optional[str] = None


class SlurmPartition(RootModel):
    root: List[str]

    def __init__(self, **kwargs):
        super().__init__(kwargs["state"])


class SlurmPartitionCPUs(RootModel):
    root: int

    def __init__(self, **kwargs):
        super().__init__(kwargs["total"])


class SlurmPartitions(PartitionModel):
    name: str = Field(validation_alias=AliasChoices("partitionName", "PartitionName"))
    cpus: int | SlurmPartitionCPUs = Field(
        validation_alias=AliasChoices("totalCPUs", "total_cpus", "TotalCPUs")
    )
    total_nodes: int = Field(validation_alias=AliasChoices("totalNodes", "TotalNodes"))
    partition: SlurmPartition | str = Field(
        validation_alias=AliasChoices("state", "State")
    )

    def __init__(self, **kwargs):

        # To allow back compatibility with Slurm API versions <= 0.0.38
        if "total_nodes" not in kwargs and "nodes" in kwargs:
            kwargs["total_nodes"] = kwargs["nodes"]["total"]
        super().__init__(**kwargs)


class SlurmReservations(ReservationModel):
    name: str = Field(
        validation_alias=AliasChoices("reservationName", "ReservationName")
    )
    node_list: str = Field(validation_alias=AliasChoices("nodes", "Nodes", "nodeList"))
    end_time: int | SlurmInt = Field(
        validation_alias=AliasChoices("endTime", "EndTime")
    )
    start_time: int | SlurmInt = Field(
        validation_alias=AliasChoices("startTime", "StartTime")
    )
    features: Optional[str] = Field(validation_alias=AliasChoices("Features"))
