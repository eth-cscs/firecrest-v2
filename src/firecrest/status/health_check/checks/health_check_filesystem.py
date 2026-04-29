# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from firecrest.config import (
    BackendServiceType,
    FilesystemServiceHealth,
    HPCCluster,
)
from firecrest.dependencies import SSHClientDependency
from firecrest.filesystem.ops.commands.ls_command import LsCommand
from firecrest.status.health_check.checks.health_check_base import HealthCheckBase


class FilesystemHealthCheck(HealthCheckBase):

    def __init__(self, auth, token, path, system: HPCCluster, timeout: int):
        super().__init__(system)
        self.timeout = timeout
        self.auth = auth
        self.token = token
        self.path = path

    async def execute_check(self) -> FilesystemServiceHealth:

        self.ssh_client = await SSHClientDependency(ignore_health=True)(
            system_name=self.system.name
        )

        health = FilesystemServiceHealth(service_type=BackendServiceType.filesystem)
        health.healthy = True
        health.path = self.path

        self.ssh_client.execute_timeout = self.timeout

        ls = LsCommand(self.path, no_recursion=True)
        async with self.ssh_client.get_client(
            self.auth.username,
            self.token["access_token"],
        ) as client:
            await client.execute(ls)

        return health

    async def handle_error(self, ex: Exception) -> FilesystemServiceHealth:
        health = FilesystemServiceHealth(service_type=BackendServiceType.filesystem)
        health.healthy = False
        health.path = self.path
        health.message = str(ex)
        return health
