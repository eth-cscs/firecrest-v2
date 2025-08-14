# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import time


from firecrest.config import DataTransferType, HealthCheckException, BaseDataTransfer
from firecrest.status.health_check.checks.health_check_s3 import S3HealthCheck
from firecrest.plugins import settings


class DataTransferHealthChecker:

    data_transfer: BaseDataTransfer = None
    checks = []

    def __init__(self, data_transfer: BaseDataTransfer):
        self.data_transfer = data_transfer

        match data_transfer.service_type:
            case DataTransferType.s3:
                s3Check = S3HealthCheck(timeout=data_transfer.probing.timeout)
                self.checks += [s3Check.check()]

    async def check(self) -> None:
        try:
            results = await asyncio.gather(*self.checks, return_exceptions=True)
            settings.data_operation.data_transfer.servicesHealth = results
        except Exception as ex:
            error_message = f"Storage HealthChecker execution failed with error: {ex.__class__.__name__}"
            if len(str(ex)) > 0:
                error_message = f"Storage HealthChecker execution failed with error: {ex.__class__.__name__} - {str(ex)}"
            exception = HealthCheckException(service_type="exception")
            exception.healthy = False
            exception.last_checked = time.time()
            exception.message = error_message
            settings.data_operation.data_transfer.servicesHealth = [exception]
            # Note: raising the exception might not be handled well by apscheduler.
            # Instead consider printing the exceotion with: traceback.print_exception(ex)
            raise ex
