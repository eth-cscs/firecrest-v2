# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# models
from typing import List, Optional, Dict
from lib.models import CamelModel

from pydantic import Field, AliasChoices


class SchedPing(CamelModel):
    hostname: Optional[str] = Field(default=None, nullable=True)
    pinged: Optional[str] = Field(default=None, nullable=True)
    latency: Optional[int] = Field(default=None, nullable=True)
    mode: Optional[str] = Field(default=None, nullable=True)


class JobStatus(CamelModel):
    state: str
    stateReason: Optional[str] = Field(default=None, nullable=True)
    exitCode: Optional[int] = Field(default=None, nullable=True)
    interruptSignal: Optional[int] = Field(default=None, nullable=True)


class JobTime(CamelModel):
    elapsed: Optional[int] = Field(default=None, nullable=True)
    start: Optional[int] = Field(default=None, nullable=True)
    end: Optional[int] = Field(default=None, nullable=True)
    suspended: Optional[int] = Field(default=None, nullable=True)
    limit: Optional[int] = Field(default=None, nullable=True)


class JobTask(CamelModel):
    id: str
    name: str
    status: JobStatus
    time: JobTime


class JobModel(CamelModel):
    job_id: str
    name: str
    status: JobStatus
    tasks: Optional[List[JobTask]] = Field(default=None, nullable=True)
    time: JobTime
    account: Optional[str] = Field(default=None, nullable=True)
    allocation_nodes: int
    cluster: str
    group: Optional[str] = Field(default=None, nullable=True)
    nodes: str
    partition: str
    kill_request_user: Optional[str] = Field(default=None, nullable=True)
    user: Optional[str]
    working_directory: str
    priority: Optional[int] = Field(default=None, nullable=True)


class JobMetadataModel(CamelModel):
    job_id: str
    script: Optional[str] = Field(default=None, nullable=True)
    standard_input: Optional[str] = Field(default=None, nullable=True)
    standard_output: Optional[str] = Field(default=None, nullable=True)
    standard_error: Optional[str] = Field(default=None, nullable=True)


class JobDescriptionModel(CamelModel):
    name: Optional[str] = Field(
        default=None, description="Name for the job", nullable=True
    )
    account: Optional[str] = Field(
        default=None,
        description="Charge job resources to specified account",
        nullable=True,
    )
    current_working_directory: str = Field(
        validation_alias=AliasChoices("workingDirectory", "working_directory"),
        description="Job working directory",
    )
    standard_input: Optional[str] = Field(
        default=None, description="Standard input file name", nullable=True
    )
    standard_output: Optional[str] = Field(
        default=None, description="Standard output file name", nullable=True
    )
    standard_error: Optional[str] = Field(
        default=None, description="Standard error file name", nullable=True
    )
    environment: Dict[str, str] | List[str] = Field(
        alias="env",
        default={"F7T_version": "v2.0.0"},
        description="Dictionary of environment variables to set in the job context",
        nullable=False,
    )
    constraints: Optional[str] = Field(
        default=None, description="Job constraints", nullable=True
    )
    script: str = Field(default=None, description="Script for the job")
    script_path: str = Field(
        default=None, description="Path to the job in target system"
    )


class JobSubmitRequestModel(CamelModel):
    pass


class NodeModel(CamelModel):
    sockets: Optional[int] = Field(default=None, nullable=True)
    cores: Optional[int] = Field(default=None, nullable=True)
    threads: Optional[int] = Field(default=None, nullable=True)
    cpus: int
    cpu_load: Optional[float] = Field(default=None, nullable=True)
    free_memory: Optional[int] = Field(default=None, nullable=True)
    features: Optional[str | List[str]] = Field(default=None, nullable=True)
    name: str
    address: Optional[str] = Field(default=None, nullable=True)
    hostname: Optional[str] = Field(default=None, nullable=True)
    state: str | List[str]
    partitions: Optional[List[str]] = Field(default=None, nullable=True)
    weight: Optional[int] = Field(default=None, nullable=True)
    alloc_memory: Optional[int] = Field(default=None, nullable=True)
    alloc_cpus: Optional[int] = Field(default=None, nullable=True)
    idle_cpus: Optional[int] = Field(default=None, nullable=True)


class ReservationModel(CamelModel):
    name: str
    node_list: str
    end_time: int
    start_time: int
    features: Optional[str] = Field(default=None, nullable=True)


class PartitionModel(CamelModel):
    name: str
    cpus: int | None = None
    total_nodes: int | None = None
    partition: str | List[str]
