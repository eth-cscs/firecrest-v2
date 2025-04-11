# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import List
from firecrest.config import HPCCluster, SchedulerServiceHealth
from firecrest.dependencies import SchedulerClientDependency
from firecrest.status.health_check.checks.health_check_base import HealthCheckBase
from lib.scheduler_clients.slurm.models import SlurmPing


class SchedulerHealthCheck(HealthCheckBase):

    def __init__(self, auth, token, system: HPCCluster, timeout: int):
        super().__init__(system)
        self.auth = auth
        self.token = token
        self.timeout = timeout

    async def execute_check(self) -> SchedulerServiceHealth:

        self.scheduler_client = await SchedulerClientDependency(ignore_health=True)(
            system_name=self.system.name
        )

        health = SchedulerServiceHealth(service_type="scheduler")
        pings: List[SlurmPing] = await self.scheduler_client.ping(
            self.auth.username, self.token["access_token"]
        )
        health.healthy = all(ping["pinged"].lower() == "up" for ping in pings)
        health.message = str(pings)
        return health

    async def handle_error(self, ex: Exception) -> SchedulerServiceHealth:
        error_message = f"{ex.__class__.__name__}"
        if len(str(ex)) > 0:
            error_message = f"{ex.__class__.__name__}: {str(ex)}"
        health = SchedulerServiceHealth(service_type="scheduler")
        health.healthy = False
        health.message = error_message
        return health
