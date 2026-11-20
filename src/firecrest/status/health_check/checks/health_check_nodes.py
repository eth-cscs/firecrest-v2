# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio

from firecrest.config import HPCCluster, BackendServiceType, NodesServiceHealth
from firecrest.dependencies import SchedulerClientDependency
from firecrest.status.health_check.checks.health_check_base import HealthCheckBase
from firecrest.status.health_check.checks.helpers import log_health_check_error


class NodesHealthCheck(HealthCheckBase):
    """Fetches the scheduler nodes; the result can be served as cached nodes info."""

    def __init__(self, auth, token, system: HPCCluster, timeout: int):
        super().__init__(system)
        self.auth = auth
        self.token = token
        self.timeout = timeout

    async def execute_check(self) -> NodesServiceHealth:

        self.scheduler_client = await SchedulerClientDependency(ignore_health=True)(
            system_name=self.system.name
        )

        async with asyncio.timeout(self.timeout):
            nodes = await self.scheduler_client.get_nodes(
                self.auth.username, self.token["access_token"]
            )

        health = NodesServiceHealth(service_type=BackendServiceType.nodes)
        if not nodes:
            health.healthy = False
            health.message = "No nodes found"
            return health

        health.healthy = True
        health.nodes = nodes
        health.message = f"{len(nodes)} nodes fetched"
        return health

    async def handle_error(self, ex: Exception) -> NodesServiceHealth:
        health = NodesServiceHealth(service_type=BackendServiceType.nodes)
        health.healthy = False
        health.message = str(ex)
        log_health_check_error(service_type=BackendServiceType.nodes,
                               health_message=health.message,
                               exception=ex,
                               system_name=self.system.name,
                               username=self.auth.username)
        return health
