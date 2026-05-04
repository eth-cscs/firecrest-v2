# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from firecrest.config import HPCCluster, BackendServiceType, SSHServiceHealth
from firecrest.dependencies import SSHClientDependency
from firecrest.status.health_check.checks.health_check_base import HealthCheckBase
from firecrest.status.health_check.checks.true_command import TrueCommand


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

        self.ssh_client.execute_timeout = self.timeout

        truecmd = TrueCommand()
        async with self.ssh_client.get_client(
            self.auth.username, self.token["access_token"]
        ) as client:
            await client.execute(truecmd)

        return health

    async def handle_error(self, ex: Exception) -> SSHServiceHealth:
        health = SSHServiceHealth(service_type=BackendServiceType.ssh)
        health.healthy = False
        health.message = str(ex)
        return health
