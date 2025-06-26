# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import List, Optional
from lib.ssh_clients.ssh_client import BaseCommand

from lib.scheduler_clients.pbs.cli_commands.qsub_command import QsubCommand
from lib.scheduler_clients.pbs.cli_commands.qstat_command import QstatCommand

from lib.scheduler_clients.pbs.cli_commands.qstat_job_metadata_command import (
    QstatJobMetadataCommand,
)

from lib.scheduler_clients.pbs.cli_commands.qdel_command import QdelCommand
from lib.scheduler_clients.pbs.cli_commands.pbsnodes_command import PbsnodesCommand

from lib.scheduler_clients.pbs.cli_commands.rstat_reservations_command import (
    RstatReservationsCommand,
)

from lib.scheduler_clients.pbs.cli_commands.pbs_partitions_command import (
    PbsPartitionsCommand,
)
from lib.scheduler_clients.pbs.cli_commands.ping_command import PbsPingCommand

# models
from lib.scheduler_clients.pbs.models import (
    PbsJob,
    PbsJobDescription,
    PbsJobMetadata,
    PbsPartition,
    PbsPing,
    PbsReservation,
    PbsNode,
)

# base client
from lib.scheduler_clients.scheduler_base_client import SchedulerBaseClient
from lib.ssh_clients.ssh_client import SSHClientPool


class PbsClient(SchedulerBaseClient):

    async def __executed_ssh_cmd(
        self,
        username: str,
        jwt_token: str,
        command: BaseCommand,
        stdin: Optional[str] = None,
    ):
        async with self.ssh_client.get_client(username, jwt_token) as client:
            return await client.execute(command, stdin)

    def __init__(
        self, ssh_client: SSHClientPool, pbs_version: str, timeout: int | None
    ):
        self.ssh_client = ssh_client
        self.pbs_version = pbs_version
        self.timeout = timeout

    async def submit_job(
        self,
        job_description: PbsJobDescription,
        username: str,
        jwt_token: str,
    ) -> str | None:
        qsub = QsubCommand(job_description=job_description)
        return await self.__executed_ssh_cmd(
            username, jwt_token, qsub, job_description.script
        )

    async def attach_command(
        self,
        command: str,
        job_id: str,
        username: str,
        jwt_token: str,
    ) -> None:
        # PBS does not have a direct equivalent to Slurm's srun overlap
        raise NotImplementedError(
            "Interactive attach is not supported in PBS CLI client"
        )

    async def get_job(
        self, job_id: str | None, username: str, jwt_token: str, allusers: bool = True
    ) -> List[PbsJob] | None:
        qstat = QstatCommand(username, [job_id] if job_id else None, allusers)
        result = await self.__executed_ssh_cmd(username, jwt_token, qstat)
        # Apply PBS model
        if result:
            result = [PbsJob.model_validate(job) for job in result]
        return result

    async def get_job_metadata(
        self, job_id: str, username: str, jwt_token: str
    ) -> List[PbsJobMetadata] | Exception | None:
        qstat_meta = QstatJobMetadataCommand(username, [job_id])
        result = await self.__executed_ssh_cmd(username, jwt_token, qstat_meta)
        # Apply PBS model
        if result:
            result = [PbsJobMetadata.model_validate(job) for job in result]
        return result

    async def get_jobs(
        self, username: str, jwt_token: str, allusers: bool = False
    ) -> List[PbsJob] | None:
        return await self.get_job(
            job_id=None, username=username, allusers=allusers, jwt_token=jwt_token
        )

    async def cancel_job(self, job_id: str, username: str, jwt_token: str) -> bool:
        qdel = QdelCommand(username=username, job_id=job_id)
        return await self.__executed_ssh_cmd(username, jwt_token, qdel)

    async def get_nodes(self, username: str, jwt_token: str) -> List[PbsNode] | None:
        nodes = PbsnodesCommand()
        res = await self.__executed_ssh_cmd(username, jwt_token, nodes)
        # Apply PBS model
        if res:
            res = [PbsNode.model_validate(node) for node in res]
        return res

    async def get_reservations(
        self, username: str, jwt_token: str
    ) -> List[PbsReservation] | None:
        reservations = RstatReservationsCommand()
        res = await self.__executed_ssh_cmd(username, jwt_token, reservations)
        # Apply PBS model
        res = [PbsReservation.model_validate(r) for r in res]
        return res

    async def get_partitions(
        self, username: str, jwt_token: str
    ) -> List[PbsPartition] | None:
        queues = PbsPartitionsCommand()
        result = await self.__executed_ssh_cmd(username, jwt_token, queues)
        # Apply PBS model
        result = [PbsPartition.model_validate(queue) for queue in result]
        return result

    async def ping(self, username: str, jwt_token: str) -> List[PbsPing] | None:
        ping_cmd = PbsPingCommand()
        return await self.__executed_ssh_cmd(username, jwt_token, ping_cmd)
