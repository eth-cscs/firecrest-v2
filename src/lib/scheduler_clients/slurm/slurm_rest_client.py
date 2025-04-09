# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
import aiohttp
from fastapi import status
from socket import AF_INET
from typing import Optional, List
from jose import jwt
from packaging.version import Version

# exceptions
from lib.exceptions import SlurmAuthTokenError, SlurmError


# models
from lib.scheduler_clients.slurm.models import (
    SlurmJob,
    SlurmJobDescription,
    SlurmJobMetadata,
    SlurmNode,
    SlurmPartitions,
    SlurmPing,
    SlurmReservations,
)
from lib.scheduler_clients.slurm.slurm_base_client import SlurmBaseClient

SIZE_POOL_AIOHTTP = 100


def _slurm_headers(username: str, jwt_token: str):
    token_claims = jwt.get_unverified_claims(jwt_token)
    if "username" not in token_claims:
        raise SlurmAuthTokenError("Claim 'username' is missing in auth token.")
    return {
        "Content-Type": "application/json",
        "X-SLURM-USER-NAME": username,
        "X-SLURM-USER-TOKEN": jwt_token,
    }


async def _slurm_unexpected_response(response):
    message = await response.text()
    raise SlurmError(
        f"Unexpected Slurm API response. status:{response.status} message:{message}"
    )


class SlurmRestClient(SlurmBaseClient):
    aiohttp_client: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_aiohttp_client(cls) -> aiohttp.ClientSession:
        if cls.aiohttp_client is None:
            timeout = aiohttp.ClientTimeout(total=60)
            connector = aiohttp.TCPConnector(
                family=AF_INET, limit_per_host=SIZE_POOL_AIOHTTP
            )
            cls.aiohttp_client = aiohttp.ClientSession(
                timeout=timeout, connector=connector
            )
        return cls.aiohttp_client

    @classmethod
    async def close_aiohttp_client(cls) -> None:
        if cls.aiohttp_client:
            await cls.aiohttp_client.close()
            cls.aiohttp_client = None

    def __init__(self, api_url: str, api_version: str, timeout: int):
        self.api_url = api_url
        self.api_version = api_version
        self.timeout = timeout

    async def submit_job(
        self,
        job_description: SlurmJobDescription,
        username: str,
        jwt_token: str,
    ) -> int | None:
        client = await self.get_aiohttp_client()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = _slurm_headers(username, jwt_token)

        # Note: starting from version "0.0.39" (included) the environment field is of type list
        if Version(self.api_version) >= Version("0.0.39") and isinstance(
            job_description.environment, dict
        ):
            job_description.environment = [
                f"{k}={v}" if v else f"{k}"
                for k, v in job_description.environment.items()
            ]

        post_data = {**{"job": job_description.model_dump(exclude_none=True)}}

        if Version(self.api_version) < Version("0.0.41"):
            # Note: starting from version "0.0.41" the script field is included in the job description
            # to allow back compatibility for version older than that we keep the old json format
            post_data = {
                **{
                    "job": job_description.model_dump(
                        exclude={"script"}, exclude_none=True
                    )
                },
                **{"script": job_description.script},
            }

        async with client.post(
            url=f"{self.api_url}/slurm/v{self.api_version}/job/submit",
            data=json.dumps(post_data),
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status != status.HTTP_200_OK:
                await _slurm_unexpected_response(response)
            job_submit_result = await response.json()
        return job_submit_result["job_id"]

    async def attach_command(
        self,
        command: str,
        job_id: str,
        username: str,
        jwt_token: str,
    ) -> int | None:
        pass

    async def get_job(
        self, job_id: str, username: str, jwt_token: str
    ) -> List[SlurmJob] | None:
        client = await self.get_aiohttp_client()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = _slurm_headers(username, jwt_token)
        async with client.get(
            url=f"{self.api_url}/slurmdb/v{self.api_version}/job/{job_id}",
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status != status.HTTP_200_OK:
                await _slurm_unexpected_response(response)
            job_result = await response.json()

            # Note: starting from API version v0.0.39 this filter can be set as query param
            jobs = list(filter(lambda job: job["user"] == username, job_result["jobs"]))
            if len(jobs) == 0:
                return None

        return jobs

    async def get_job_metadata(
        self, job_id: str, username: str, jwt_token: str
    ) -> List[SlurmJobMetadata]:
        # Until version 4.05.1 slurmdb/job end-point does not provide stdout & stderr information
        raise NotImplementedError("This method is not supported by the Slurm REST API")

    async def get_jobs(self, username: str, jwt_token: str) -> List[SlurmJob] | None:
        client = await self.get_aiohttp_client()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = _slurm_headers(username, jwt_token)
        async with client.get(
            url=f"{self.api_url}/slurmdb/v{self.api_version}/jobs",
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status != status.HTTP_200_OK:
                await _slurm_unexpected_response(response)
            job_result = await response.json()

            # Note: starting from API version v0.0.39 this filter can be set as query param
            jobs = list(filter(lambda job: job["user"] == username, job_result["jobs"]))
            if len(jobs) == 0:
                return None

        return jobs

    async def cancel_job(self, job_id: str, username: str, jwt_token: str) -> bool:
        client = await self.get_aiohttp_client()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = _slurm_headers(username, jwt_token)
        async with client.delete(
            url=f"{self.api_url}/slurm/v{self.api_version}/job/{job_id}",
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status == status.HTTP_200_OK:
                return True
            await _slurm_unexpected_response(response)

    async def get_nodes(self, username: str, jwt_token: str) -> List[SlurmNode] | None:
        client = await self.get_aiohttp_client()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = _slurm_headers(username, jwt_token)
        async with client.get(
            url=f"{self.api_url}/slurm/v{self.api_version}/nodes",
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status != status.HTTP_200_OK:
                await _slurm_unexpected_response(response)
            nodes_result = await response.json()
            if len(nodes_result["nodes"]) == 0:
                return None
        return nodes_result["nodes"]

    async def get_reservations(
        self, username: str, jwt_token: str
    ) -> List[SlurmReservations] | None:
        client = await self.get_aiohttp_client()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = _slurm_headers(username, jwt_token)
        async with client.get(
            url=f"{self.api_url}/slurm/v{self.api_version}/reservations",
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status != status.HTTP_200_OK:
                await _slurm_unexpected_response(response)
            reservation_result = await response.json()
            if len(reservation_result["reservations"]) == 0:
                return []
        return reservation_result["reservations"]

    async def get_partitions(
        self, username: str, jwt_token: str
    ) -> List[SlurmPartitions] | None:
        client = await self.get_aiohttp_client()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = _slurm_headers(username, jwt_token)
        async with client.get(
            url=f"{self.api_url}/slurm/v{self.api_version}/partitions",
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status != status.HTTP_200_OK:
                await _slurm_unexpected_response(response)
            partition_result = await response.json()
            if len(partition_result["partitions"]) == 0:
                return []
        return partition_result["partitions"]

    async def ping(self, username: str, jwt_token: str) -> List[SlurmPing] | None:
        client = await self.get_aiohttp_client()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = _slurm_headers(username, jwt_token)
        async with client.get(
            url=f"{self.api_url}/slurm/v{self.api_version}/ping",
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status != status.HTTP_200_OK:
                await _slurm_unexpected_response(response)
            partition_result = await response.json()
            if len(partition_result["pings"]) == 0:
                return []
        return partition_result["pings"]
