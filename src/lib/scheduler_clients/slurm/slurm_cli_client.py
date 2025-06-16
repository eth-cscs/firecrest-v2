# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
from typing import List
from packaging.version import Version

# models
from lib.scheduler_clients.slurm.cli_commands.sacct_batch_script_command import (
    SacctBatchScriptCommand,
)
from lib.scheduler_clients.slurm.cli_commands.sacct_job_info_command import SacctCommand
from lib.scheduler_clients.slurm.cli_commands.sacct_job_metadata_command import (
    SacctJobMetadataCommand,
)
from lib.scheduler_clients.slurm.cli_commands.sbatch_command import SbatchCommand
from lib.scheduler_clients.slurm.cli_commands.scancel_command import ScancelCommand
from lib.scheduler_clients.slurm.cli_commands.scontrol_batch_script_command import (
    ScontrolBatchScriptCommand,
)
from lib.scheduler_clients.slurm.cli_commands.scontrol_job_command import (
    ScontrolJobCommand,
)
from lib.scheduler_clients.slurm.cli_commands.scontrol_partitions_command import (
    ScontrolPartitionCommand,
)
from lib.scheduler_clients.slurm.cli_commands.scontrol_ping import ScontrolPingCommand
from lib.scheduler_clients.slurm.cli_commands.scontrol_reservations_command import (
    ScontrolReservationCommand,
)
from lib.scheduler_clients.slurm.cli_commands.sinfo_command import SinfoCommand
from lib.scheduler_clients.slurm.cli_commands.srun_command import SrunCommand
from lib.scheduler_clients.slurm.models import (
    SlurmJob,
    SlurmJobDescription,
    SlurmJobMetadata,
    SlurmPartitions,
    SlurmPing,
    SlurmReservations,
    SlurmNode,
)

# clients
from lib.scheduler_clients.slurm.slurm_base_client import SlurmBaseClient
from lib.ssh_clients.ssh_client import SSHClientPool


class SlurmCliClient(SlurmBaseClient):

    async def __executed_ssh_cmd(self, username, jwt_token, command, stdin=None):
        async with self.ssh_client.get_client(username, jwt_token) as client:
            return await client.execute(command, stdin)

    def __init__(
        self,
        ssh_client: SSHClientPool,
        slurm_version: str,
    ):
        self.ssh_client = ssh_client
        self.slurm_version = slurm_version

    async def submit_job(
        self,
        job_description: SlurmJobDescription,
        username: str,
        jwt_token: str,
    ) -> int | None:
        sbatch = SbatchCommand(job_description=job_description)
        return await self.__executed_ssh_cmd(
            username, jwt_token, sbatch, job_description.script
        )

    async def attach_command(
        self,
        command: str,
        job_id: str,
        username: str,
        jwt_token: str,
    ) -> int | None:
        srun = SrunCommand(command=command, job_id=job_id, overlap=True)
        return await self.__executed_ssh_cmd(username, jwt_token, srun)

    async def get_job(
        self, job_id: str | None, username: str, jwt_token: str, allusers: bool = True
    ) -> List[SlurmJob] | None:
        sacct = SacctCommand(username, [job_id] if job_id else None, allusers)
        jobs = await self.__executed_ssh_cmd(username, jwt_token, sacct)
        if jobs:
            # Apply Slurm model
            jobs = [SlurmJob.model_validate(job) for job in jobs]
        return jobs

    async def get_job_metadata(
        self, job_id: str, username: str, jwt_token: str
    ) -> List[SlurmJobMetadata]:

        # Note:
        # sacct --format="StdOut,StdIn,StdErr" and batch-script require custom config
        # add flag AccountingStoreFlags=job_env,job_script in slurm.conf to enable it

        scontrol = ScontrolJobCommand(job_id if job_id else None)
        scontrol_script = ScontrolBatchScriptCommand(job_id if job_id else None)
        commands = [
            self.__executed_ssh_cmd(username, jwt_token, scontrol),
            self.__executed_ssh_cmd(username, jwt_token, scontrol_script),
        ]

        if Version(self.slurm_version) >= Version("24.05.0"):
            sacct = SacctJobMetadataCommand(username, [job_id] if job_id else None)
            sacct_script = SacctBatchScriptCommand(
                username, [job_id] if job_id else None
            )
            commands += [
                self.__executed_ssh_cmd(username, jwt_token, sacct),
                self.__executed_ssh_cmd(username, jwt_token, sacct_script),
            ]

        results = await asyncio.gather(*commands, return_exceptions=True)

        cmd_result_i: int = 0

        # check if job was found
        if not results[cmd_result_i]:
            return None

        # fallback to sacct command if scontrol failed to retrieve job info
        if not isinstance(results[cmd_result_i], list) and len(results) == 4:
            cmd_result_i = 2

        if results[cmd_result_i] is None:
            return None
        if isinstance(results[cmd_result_i], Exception):
            return results[cmd_result_i]

        jobs = []
        for i in range(len(results[cmd_result_i])):
            jobs.append(
                SlurmJobMetadata(
                    **{**results[cmd_result_i][i], **results[cmd_result_i + 1][i]}
                )
            )

        return jobs

    async def get_jobs(
        self, username: str, jwt_token: str, allusers: bool = False
    ) -> List[SlurmJob] | None:
        return await self.get_job(
            job_id=None, username=username, jwt_token=jwt_token, allusers=allusers
        )

    async def cancel_job(self, job_id: str, username: str, jwt_token: str) -> bool:
        scancel = ScancelCommand(username, job_id)
        return await self.__executed_ssh_cmd(username, jwt_token, scancel)

    async def get_nodes(self, username: str, jwt_token: str) -> List[SlurmNode] | None:
        sinfo = SinfoCommand()
        return await self.__executed_ssh_cmd(username, jwt_token, sinfo)

    async def get_reservations(
        self, username: str, jwt_token: str
    ) -> List[SlurmReservations] | None:
        scontrolreservation = ScontrolReservationCommand()
        result = await self.__executed_ssh_cmd(username, jwt_token, scontrolreservation)
        # Apply Slurm model
        if result:
            result = [
                SlurmReservations.model_validate(reservation) for reservation in result
            ]
        return result

    async def get_partitions(
        self, username: str, jwt_token: str
    ) -> List[SlurmPartitions] | None:
        scontrolpartition = ScontrolPartitionCommand()
        result = await self.__executed_ssh_cmd(username, jwt_token, scontrolpartition)
        if result:
            result = [
                SlurmPartitions.model_validate(reservation) for reservation in result
            ]
        return result

    async def ping(self, username: str, jwt_token: str) -> List[SlurmPing] | None:
        scontrolping = ScontrolPingCommand()
        return await self.__executed_ssh_cmd(username, jwt_token, scontrolping)
