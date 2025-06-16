# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# models
from typing import List, Optional, Dict
from lib.models import CamelModel

from pydantic import Field


class SchedPing(CamelModel):
    hostname: Optional[str] = None
    pinged: Optional[str] = None
    latency: Optional[int] = None
    mode: Optional[str] = None


class JobStatus(CamelModel):
    state: str
    stateReason: Optional[str] = None
    exitCode: Optional[int] = None
    interruptSignal: Optional[int] = None


class JobTime(CamelModel):
    elapsed: Optional[int] = None
    start: Optional[int] = None
    end: Optional[int] = None
    suspended: Optional[int] = None
    limit: Optional[int] = None


class JobTask(CamelModel):
    id: str
    name: str
    status: JobStatus
    time: JobTime


class JobModel(CamelModel):
    job_id: int
    name: str
    status: JobStatus
    tasks: Optional[List[JobTask]] = None
    time: JobTime
    account: Optional[str]
    allocation_nodes: int
    cluster: str
    group: str
    nodes: str
    partition: str
    kill_request_user: Optional[str] = None
    user: Optional[str]
    working_directory: str
    priority: Optional[int] = None


class JobMetadataModel(CamelModel):
    job_id: int
    script: Optional[str] = None
    standard_input: Optional[str] = None
    standard_output: Optional[str] = None
    standard_error: Optional[str] = None


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
    state: str | List[str]
    partitions: List[str]
    weight: int
    alloc_memory: Optional[int] = None
    alloc_cpus: Optional[int] = None
    idle_cpus: Optional[int] = None


class ReservationModel(CamelModel):
    name: str
    node_list: str
    end_time: int
    start_time: int
    features: Optional[str] = None


class PartitionModel(CamelModel):
    name: str
    cpus: int
    total_nodes: int
    partition: str | List[str]
