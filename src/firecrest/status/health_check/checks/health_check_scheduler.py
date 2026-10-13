# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import List
from firecrest.config import HPCCluster, BackendServiceType, SchedulerServiceHealth
from firecrest.dependencies import SchedulerClientDependency
from firecrest.status.health_check.checks.health_check_base import HealthCheckBase
from lib.scheduler_clients.models import SchedPing

import logging


def ping_is_up(ping) -> bool:
    """Whether a scheduler ping entry reports a responding controller.

    Slurm's data_parser deprecated the string ``pinged`` ("UP"/"DOWN") and
    ``mode`` fields in v0.0.44 (Slurm 25.11) in favour of the boolean
    ``responding`` and ``primary``, and dropped the old fields in v0.0.45
    (Slurm 26.05). The CLI client (``scontrol ping``) still produces
    ``pinged``. Accept both shapes so the probe works across the supported
    ``api_version`` range. Both scheduler clients return the pings as plain
    dicts.
    """
    if "responding" in ping:
        return bool(ping["responding"])
    else:
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
        logger = logging.getLogger("uvicorn.error")

        log_data = {}

        log_data["message"] = (
            f"Scheduler Health check for {self.system.name if self.system else 'unknown system'} failed: {health.message if ex else 'Unknown exception'}"
        )

        log_data["error.type"] = ex.__class__.__name__ if ex else "SchedulerConnectionError"
        if ex:
            log_data["error.message"] = (
                ex.__class__.__name__ + ": " + health.message
            )
        else:
            log_data["error.message"] = "Unknown Scheduler connection exception"

        log_data["firecrest.username"] = self.auth.username

        logger.error(log_data)
        return health
