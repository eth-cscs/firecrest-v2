# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import Dict, Optional

from pydantic import AliasChoices, Field, validator

# models
from lib.models.base_model import CamelModel
from lib.scheduler_clients.models import (
    JobMetadataModel,
    JobModel,
    JobDescriptionModel,
    JobTime,
    NodeModel,
    PartitionModel,
    ReservationModel,
)

from datetime import datetime


class PbsJobDescription(JobDescriptionModel):
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
    environment: Optional[Dict[str, str]] = Field(
        alias="env",
        default={"F7T_version": "v2.0.0"},
        description="Environment variables to set in the job context",
    )
    queue: Optional[str] = Field(default=None, description="Queue to submit to")
    resources: Optional[str] = Field(
        default=None,
        description="Resource requirements (e.g. nodes, ppn, mem, walltime)",
    )
    script: str = Field(description="Script for the job")
    script_path: str = Field(
        default=None, description="Path to the job in target system"
    )


class PbsJobMetadata(JobMetadataModel):
    job_id: str = Field(alias=AliasChoices("jobId", "job_id"))
    script: None = None
    standard_input: None = Field(
        validation_alias=AliasChoices("StdIn", "standardInput"), default=None
    )
    standard_output: Optional[str] = Field(
        validation_alias=AliasChoices("StdOut", "standardOutput"), default=None
    )
    standard_error: Optional[str] = Field(
        validation_alias=AliasChoices("StdErr", "standardError"), default=None
    )


class JobTimePbs(JobTime):
    # Start and elapsed appear after the job is started
    start: Optional[int] = None
    elapsed: Optional[int] = None
    end: None = None
    suspended: None = None

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
                raise ValueError(f"invalid duration string: {v!r}")
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


class PbsJob(JobModel):
    tasks: None = None
    time: JobTimePbs
    account: str
    allocation_nodes: int
    cluster: str
    nodes: str
    partition: str
    priority: int
    user: str
    working_directory: str


class PbsNode(NodeModel):
    name: str
    state: str
    cpus: int
    memory: str


class PbsPing(CamelModel):
    hostname: Optional[str] = None
    pinged: Optional[str] = None
    latency: Optional[int] = None
    mode: Optional[str] = None


class PbsPartition(PartitionModel):
    name: str
    cpus: int
    total_nodes: int
    partition: str = Field(validation_alias=AliasChoices("state", "State"))


class PbsReservation(ReservationModel):
    resv_id: str = Field(default=None, alias=AliasChoices("resvId", "reservationId"))
    name: str = Field(validation_alias=AliasChoices("resvName", "ReservationName"))
    owner: str
    state: str
    # queue: Optional[str] = Field(default=None, alias=AliasChoices("queueName", "queue"))
    node_list: str = Field(validation_alias=AliasChoices("nodes", "Nodes", "nodeList"))
    start_time: Optional[str] = Field(
        default=None, alias=AliasChoices("startTime", "start_time")
    )
    end_time: Optional[str] = Field(
        default=None, alias=AliasChoices("endTime", "end_time")
    )
