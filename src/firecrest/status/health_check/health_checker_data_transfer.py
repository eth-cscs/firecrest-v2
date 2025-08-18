# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import time


from firecrest.config import DataTransferType, HealthCheckException, BaseDataTransfer
from firecrest.status.health_check.checks.health_check_s3 import S3HealthCheck


class DataTransferHealthChecker:

    data_transfer: BaseDataTransfer = None

    def __init__(self, data_transfer: BaseDataTransfer):
        self.data_transfer = data_transfer

    async def check(self) -> None:
        checks = []
        match self.data_transfer.service_type:
            case DataTransferType.s3:
                s3Check = S3HealthCheck(timeout=self.data_transfer.probing.timeout)
                checks += [s3Check.check()]

        try:
            results = await asyncio.gather(*checks, return_exceptions=True)
            self.data_transfer.servicesHealth = results
        except Exception as ex:
            error_message = f"DataTransfer HealthChecker execution failed with error: {ex.__class__.__name__}"
            if len(str(ex)) > 0:
                error_message = f"DataTransfer HealthChecker execution failed with error: {ex.__class__.__name__} - {str(ex)}"
            exception = HealthCheckException(service_type="exception")
            exception.healthy = False
            exception.last_checked = time.time()
            exception.message = error_message
            self.data_transfer.servicesHealth = [exception]
            # Note: raising the exception might not be handled well by apscheduler.
            # Instead consider printing the exceotion with: traceback.print_exception(ex)
            raise ex
