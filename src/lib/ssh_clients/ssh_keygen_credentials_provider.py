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
from lib.ssh_clients.ssh_credentials_provider import SSHCredentialsProvider
from lib.request_vars import g

SIZE_POOL_AIOHTTP = 100


def _ssh_service_headers(jwt_token: str, app_version: str) -> dict:
    ctx = g()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jwt_token}",
        "x-client-type": getattr(ctx, "x_client_type", None) or "api",
        "x-client-name": getattr(ctx, "x_client_name", None) or "firecrest",
        "x-client-version": getattr(ctx, "x_client_version", None) or app_version,
    }
    x_request_id = getattr(ctx, "x_request_id", None)
    if x_request_id:
        headers["x-request-id"] = x_request_id
    return headers


class SSHKeygenCredentialsProvider(SSHCredentialsProvider):
    aiohttp_client: Optional[aiohttp.ClientSession] = None
    max_connections: int = 0

    @classmethod
    async def get_aiohttp_client(cls) -> aiohttp.ClientSession:
        if cls.aiohttp_client is None:
            timeout = aiohttp.ClientTimeout(total=5)
            connector = aiohttp.TCPConnector(
                family=AF_INET,
                limit_per_host=SSHKeygenCredentialsProvider.max_connections,
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

    def __init__(self, ssh_keygen_url: str, max_connections: int = 100, app_version: str = ""):
        self.ssh_keygen_url = ssh_keygen_url
        self.app_version = app_version
        SSHKeygenCredentialsProvider.max_connections = max_connections

    async def get_credentials(self, username: str, jwt_token: str):
        client = await self.get_aiohttp_client()
        headers = _ssh_service_headers(jwt_token, self.app_version)

        post_data = {
            "duration": "1min",
            "username": username,
        }

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
            response = await response.json()
            return SSHCredentialsProvider.SSHCredentials(
                **{
                    "private_key": response["sshKey"]["privateKey"] + "\n",
                    "public_certificate": response["sshKey"]["publicKey"] + "\n",
                }
            )
