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


# exceptions
from lib.exceptions import SSHServiceError
from lib.ssh_clients.ssh_credentials_provider import SSHCredentialsProvider

SIZE_POOL_AIOHTTP = 100


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

    def __init__(self, ssh_keygen_url: str, max_connections: int = 100):
        self.ssh_keygen_url = ssh_keygen_url
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

        private, public = self.genkeys()
        post_data = {"PublicKey": public, "OTT": jwt_token}

        async with client.post(
            url=f"{self.ssh_keygen_url}/sign",
            data=json.dumps(post_data),
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
