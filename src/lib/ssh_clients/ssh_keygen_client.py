# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
import aiohttp
from fastapi import status
from socket import AF_INET
from typing import Optional


# exceptions
from lib.exceptions import SSHServiceError
from lib.ssh_clients.ssh_key_provider import SSHKeysProvider

SIZE_POOL_AIOHTTP = 100


def _ssh_service_headers(jwt_token: str):
    return {"Content-Type": "application/json", "Authorization": f"Bearer {jwt_token}"}


class SSHKeygenClient(SSHKeysProvider):
    aiohttp_client: Optional[aiohttp.ClientSession] = None
    max_connections: int = 0

    @classmethod
    async def get_aiohttp_client(cls) -> aiohttp.ClientSession:
        if cls.aiohttp_client is None:
            timeout = aiohttp.ClientTimeout(total=5)
            connector = aiohttp.TCPConnector(
                family=AF_INET, limit_per_host=SSHKeygenClient.max_connections
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

    def __init__(self, ssh_keygen_url: str, max_connections: int = 100):
        self.ssh_keygen_url = ssh_keygen_url
        SSHKeygenClient.max_connections = max_connections

    async def get_keys(self, username: str, jwt_token: str):
        client = await self.get_aiohttp_client()
        headers = _ssh_service_headers(jwt_token)

        post_data = {"duration": "1min"}

        async with client.post(
            url=f"{self.ssh_keygen_url}/api/v1/ssh-keys",
            data=json.dumps(post_data),
            headers=headers,
        ) as response:
            if response.status != status.HTTP_201_CREATED:
                message = await response.text()
                raise SSHServiceError(
                    f"Unexpected SSHService response. status:{response.status} message:{message}"
                )
            job_submit_result = await response.json()
            job_submit_result["sshKey"]["passphrase"] = None
        return job_submit_result["sshKey"]
