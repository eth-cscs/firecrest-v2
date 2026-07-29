# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
import aiohttp
from fastapi import status
from socket import AF_INET
from typing import Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from starlette_context import context
from starlette_context.header_keys import HeaderKeys

# exceptions
from lib.exceptions import SSHServiceError
from lib.ssh_clients.ssh_credentials_provider import SSHCredentialsProvider

SIZE_POOL_AIOHTTP = 100


def _ssh_service_headers(app_version: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "x-client-type": "api",
        "x-client-name": "firecrest",
        "x-client-version": app_version,
    }
    if context.exists():
        if HeaderKeys.request_id in context:
            headers["x-request-id"] = context[HeaderKeys.request_id]
        if HeaderKeys.correlation_id in context:
            headers["x-trace-id"] = context[HeaderKeys.correlation_id]
    return headers


class DeiCSSHCACredentialsProvider(SSHCredentialsProvider):
    aiohttp_client: Optional[aiohttp.ClientSession] = None
    max_connections: int = 0

    @classmethod
    async def get_aiohttp_client(cls) -> aiohttp.ClientSession:
        if cls.aiohttp_client is None:
            timeout = aiohttp.ClientTimeout(total=5)
            connector = aiohttp.TCPConnector(
                family=AF_INET,
                limit_per_host=DeiCSSHCACredentialsProvider.max_connections,
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

    def __init__(self, ssh_keygen_url: str, max_connections: int = 100, *, app_version: str):
        self.ssh_keygen_url = ssh_keygen_url
        self.app_version = app_version
        DeiCSSHCACredentialsProvider.max_connections = max_connections

    def genkeys(self):

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        raw_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        )

        raw_public = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        )

        return raw_private.decode(), raw_public.decode()

    async def get_credentials(
        self, username: str, jwt_token: str
    ) -> SSHCredentialsProvider.SSHCredentials:

        client = await self.get_aiohttp_client()
        headers = _ssh_service_headers(self.app_version)

        private, public = self.genkeys()
        post_data = {"PublicKey": public, "OTT": jwt_token}

        async with client.post(
            url=f"{self.ssh_keygen_url}/sign",
            data=json.dumps(post_data),
            headers=headers,
        ) as response:
            if response.status != status.HTTP_200_OK:
                message = await response.text()
                raise SSHServiceError(
                    f"Unexpected SSHService response. status:{response.status} message:{message}"
                )
            certificate = await response.text()
            return SSHCredentialsProvider.SSHCredentials(
                **{
                    "private_key": private,
                    "public_certificate": certificate,
                }
            )
