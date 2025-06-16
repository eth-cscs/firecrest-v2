from typing import List

from lib.scheduler_clients.slurm.models import (
    SlurmJob,
    SlurmJobDescription,
    SlurmJobMetadata,
    SlurmPartitions,
    SlurmPing,
    SlurmReservations,
    SlurmNode,
)

from lib.scheduler_clients.slurm.slurm_base_client import SlurmBaseClient
from lib.scheduler_clients.slurm.slurm_cli_client import SlurmCliClient
from lib.scheduler_clients.slurm.slurm_rest_client import SlurmRestClient

from lib.ssh_clients.ssh_client import SSHClientPool


class SlurmClient(SlurmBaseClient):

    def __init__(
        self,
        ssh_client: SSHClientPool,
        slurm_version: str,
        api_version: str | None,
        api_url: str | None,
        timeout: int | None,
    ):

        self.ssh_client = ssh_client
        self.api_url = api_url
        self.timeout = timeout
        self.slurm_version = slurm_version
        self.api_version = api_version

        self.slurm_cli_client = SlurmCliClient(ssh_client, slurm_version)

        if self.api_url:
            self.slurm_rest_client = SlurmRestClient(api_url, api_version, timeout)
            self.slurm_default_client = self.slurm_rest_client
        else:
            self.slurm_default_client = self.slurm_cli_client

    async def submit_job(
        self,
        job_description: SlurmJobDescription,
        username: str,
        jwt_token: str,
    ) -> int | None:

        if job_description.script_path:
            return await self.slurm_cli_client.submit_job(
                job_description, username, jwt_token
            )

        return await self.slurm_default_client.submit_job(
            job_description, username, jwt_token
        )

    async def attach_command(
        self, command: str, job_id: str, username: str, jwt_token: str
    ) -> int | None:
        return await self.slurm_default_client.attach_command(
            command, job_id, username, jwt_token
        )

    async def get_job(
        self, job_id: str | None, username: str, jwt_token: str, allusers: bool = True
    ) -> List[SlurmJob] | None:
        return await self.slurm_default_client.get_job(
            job_id, username, jwt_token, allusers
        )

    async def get_jobs(
        self, username: str, jwt_token: str, allusers: bool = False
    ) -> List[SlurmJob] | None:
        return await self.slurm_default_client.get_jobs(username, jwt_token, allusers)

    async def get_job_metadata(
        self, job_id: str, username: str, jwt_token: str
    ) -> List[SlurmJobMetadata]:
        return await self.slurm_cli_client.get_job_metadata(job_id, username, jwt_token)

    async def get_nodes(self, username: str, jwt_token: str) -> List[SlurmNode] | None:
        return await self.slurm_default_client.get_nodes(username, jwt_token)

    async def get_reservations(
        self, username: str, jwt_token: str
    ) -> List[SlurmReservations] | None:
        return await self.slurm_default_client.get_reservations(username, jwt_token)

    async def get_partitions(
        self, username: str, jwt_token: str
    ) -> List[SlurmPartitions] | None:
        return await self.slurm_default_client.get_partitions(username, jwt_token)

    async def cancel_job(self, job_id: str, username: str, jwt_token: str) -> bool:
        return await self.slurm_default_client.cancel_job(job_id, username, jwt_token)

    async def ping(self, username: str, jwt_token: str) -> List[SlurmPing] | None:
        return await self.slurm_default_client.ping(username, jwt_token)
