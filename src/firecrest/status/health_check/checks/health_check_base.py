# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import time

from firecrest.config import BaseServiceHealth, HPCCluster


class HealthCheckBase(ABC):

    def __init__(self, system: HPCCluster = None):
        self.system = system

    async def check(self) -> BaseServiceHealth:
        health: BaseServiceHealth
        start_time = time.monotonic_ns()
        start_check = datetime.now(timezone.utc)

        # Execute the check
        try:
            health = await self.execute_check()
        except Exception as ex:
            health = await self.handle_error(ex)

        # Compute latency in seconds
        health.latency = (time.monotonic_ns() - start_time) / 1e9
        health.last_checked = start_check
        return health

    @abstractmethod
    async def execute_check(self) -> BaseServiceHealth:
        pass

    @abstractmethod
    async def handle_error(self, ex: Exception) -> BaseServiceHealth:
        pass
