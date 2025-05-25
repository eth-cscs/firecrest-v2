# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import time


from firecrest.config import HealthCheckException, Storage
from firecrest.status.health_check.checks.health_check_s3 import S3HealthCheck
from firecrest.plugins import settings


class StorageHealthChecker:

    storage: Storage = None

    def __init__(self, storage: Storage):
        self.storage = storage

    async def check(self) -> None:
        try:
            checks = []
            s3Check = S3HealthCheck(timeout=settings.storage.probing.timeout)
            checks += [s3Check.check()]

            results = await asyncio.gather(*checks, return_exceptions=True)
            self.storage.servicesHealth = results
        except Exception as ex:
            error_message = f"Storage HealthChecker execution failed with error: {ex.__class__.__name__}"
            if len(str(ex)) > 0:
                error_message = f"Storage HealthChecker execution failed with error: {ex.__class__.__name__} - {str(ex)}"
            exception = HealthCheckException(service_type="exception")
            exception.healthy = False
            exception.last_checked = time.time()
            exception.message = error_message
            self.storage.servicesHealth = [exception]
            # Note: raising the exception might not be handled well by apscheduler.
            # Instead consider printing the exceotion with: traceback.print_exception(ex)
            raise ex
