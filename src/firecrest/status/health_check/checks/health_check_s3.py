# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from firecrest.config import (
    HPCCluster,
    S3ServiceHealth,
)
from firecrest.dependencies import (
    S3ClientConnectionType,
    S3ClientDependency,
)
from firecrest.status.health_check.checks.health_check_base import HealthCheckBase
from fastapi import Depends


class S3HealthCheck(HealthCheckBase):

    def __init__(self, system: HPCCluster, timeout: int):
        super().__init__(system)
        self.timeout = timeout

    async def execute_check(self) -> S3ServiceHealth:

        health = S3ServiceHealth(service_type="s3")
        health.healthy = True

        async with await S3ClientDependency(
            connection=S3ClientConnectionType.private
        )() as s3_client:

            buckets = await s3_client.list_buckets(MaxBuckets=1)

        return health

    async def handle_error(self, ex: Exception) -> S3ServiceHealth:
        health = S3ServiceHealth(service_type="s3")
        health.healthy = False
        health.message = str(ex)
        return health
