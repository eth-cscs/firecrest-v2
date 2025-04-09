# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import List
from abc import ABC, abstractmethod

# models
from lib.scheduler_clients.models import (
    JobMetadataModel,
    JobModel,
    JobDescriptionModel,
    NodeModel,
    PartitionModel,
    ReservationModel,
)


class SchedulerBaseClient(ABC):

    @abstractmethod
    async def submit_job(
        self,
        job_description: JobDescriptionModel,
        username: str,
        jwt_token: str,
    ) -> int | None:
        pass

    @abstractmethod
    async def attach_command(
        self,
        command: str,
        job_id: str,
        username: str,
        jwt_token: str,
    ) -> int | None:
        pass

    @abstractmethod
    # Note: returns multiple jobs to deal with job_id duplicates (see Slurm doc)
    async def get_job(
        self, job_id: str, username: str, jwt_token: str
    ) -> List[JobModel]:
        pass

    @abstractmethod
    # Note: returns multiple jobs to deal with job_id duplicates (see Slurm doc)
    async def get_job_metadata(
        self, job_id: str, username: str, jwt_token: str
    ) -> List[JobMetadataModel]:
        pass

    @abstractmethod
    async def get_jobs(self, username: str, jwt_token: str) -> List[JobModel] | None:
        pass

    @abstractmethod
    async def cancel_job(self, job_id: str, username: str, jwt_token: str) -> bool:
        pass

    @abstractmethod
    async def get_nodes(self, username: str, jwt_token: str) -> List[NodeModel] | None:
        pass

    @abstractmethod
    async def get_reservations(
        self, username: str, jwt_token: str
    ) -> List[ReservationModel] | None:
        pass

    @abstractmethod
    async def get_partitions(
        self, username: str, jwt_token: str
    ) -> List[PartitionModel] | None:
        pass
