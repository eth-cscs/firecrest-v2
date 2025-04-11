# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from socket import AF_INET
import aiohttp
from fastapi import HTTPException, status

from lib.auth.authZ.authorization_service import AuthorizationService


class OpenFGAClient(AuthorizationService):

    class BearerAuth(aiohttp.BasicAuth):
        def __init__(self, token: str):
            self.token = token

        def encode(self) -> str:
            return f"Bearer {self.token}"

    def __init__(
        self, url: str = None, timeout: int = None, max_connections: int = 0
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.max_connections = max_connections

    async def authorize(self, username: str, resource_name: str, access_token: str):

        if self.url is None:
            return

        auth_token = OpenFGAClient.BearerAuth(access_token)

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            connector = aiohttp.TCPConnector(
                family=AF_INET, limit_per_host=self.max_connections
            )

            async with aiohttp.ClientSession(
                timeout=timeout, connector=connector
            ) as session:
                async with session.post(
                    url=self.url,
                    auth=auth_token,
                    json={
                        "user": f"user:{username}",
                        "relation": "member",
                        "object": f"vcluster:{resource_name}",
                    },
                ) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not authorized to access system",
                        )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to verify system access authorization",
            ) from exc
