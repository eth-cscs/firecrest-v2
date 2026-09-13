# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import List
from firecrest.config import HPCCluster, BackendServiceType, SchedulerServiceHealth
from firecrest.dependencies import SchedulerClientDependency
from firecrest.status.health_check.checks.health_check_base import HealthCheckBase
from lib.scheduler_clients.models import SchedPing


def ping_is_up(ping) -> bool:
    """Whether a scheduler ping entry reports a responding controller.

    Slurm's data_parser deprecated the string ``pinged`` ("UP"/"DOWN") and
    ``mode`` fields in v0.0.44 (Slurm 25.11) in favour of the boolean
    ``responding`` and ``primary``, and dropped the old fields in v0.0.45
    (Slurm 26.05). The CLI client (``scontrol ping``) still produces
    ``pinged``. Accept both shapes so the probe works across the supported
    ``api_version`` range.
    """
    if isinstance(ping, SchedPing):
        ping = ping.model_dump()
    responding = ping.get("responding")
    if responding is not None:
        return bool(responding)
    return str(ping.get("pinged") or "").lower() == "up"


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

        health = SchedulerServiceHealth(service_type=BackendServiceType.scheduler)
        pings: List[SchedPing] = await self.scheduler_client.ping(
            self.auth.username, self.token["access_token"]
        )
        health.healthy = all(ping_is_up(ping) for ping in pings)
        health.message = str(pings)
        return health

    async def handle_error(self, ex: Exception) -> SchedulerServiceHealth:
        error_message = f"{ex.__class__.__name__}"
        if len(str(ex)) > 0:
            error_message = f"{ex.__class__.__name__}: {str(ex)}"
        health = SchedulerServiceHealth(service_type=BackendServiceType.scheduler)
        health.healthy = False
        health.message = error_message
        return health
