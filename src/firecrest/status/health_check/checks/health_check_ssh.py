# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio

from firecrest.config import HPCCluster, BackendServiceType, SSHServiceHealth
from firecrest.dependencies import SSHClientDependency
from firecrest.status.health_check.checks.health_check_base import HealthCheckBase
from firecrest.status.health_check.checks.true_command import TrueCommand

import logging


class SSHHealthCheck(HealthCheckBase):

    def __init__(self, auth, token, system: HPCCluster, timeout: int):
        super().__init__(system)
        self.auth = auth
        self.token = token
        self.timeout = timeout

    async def execute_check(self) -> SSHServiceHealth:

        self.ssh_client = await SSHClientDependency(ignore_health=True)(
            system_name=self.system.name
        )

        health = SSHServiceHealth(service_type=BackendServiceType.ssh)
        health.healthy = True

        truecmd = TrueCommand()
        async with self.ssh_client.get_client(
            self.auth.username, self.token["access_token"]
        ) as client:
            async with asyncio.timeout(self.timeout):
                await client.execute(truecmd)
        return health

    async def handle_error(self, ex: Exception) -> SSHServiceHealth:
        health = SSHServiceHealth(service_type=BackendServiceType.ssh)
        health.healthy = False
        health.message = str(ex)
        logger = logging.getLogger("uvicorn.error")
        log_data = {}

        log_data["message"] = (
            f"SSH Health check for {self.system.name if self.system else 'unknown system'} failed: {health.message if ex else 'Unknown SSH connection exception'}"
        )

        log_data["error.type"] = ex.__class__.__name__ if ex else "SSHConnectionError"
        if ex:
            log_data["error.message"] = (
                ex.__class__.__name__ + ": " + health.message
            )
        else:
            log_data["error.message"] = "Unknown SSH connection exception"

        log_data["firecrest.username"] = self.auth.username

        logger.error(log_data)
        return health
