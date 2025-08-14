# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from firecrest.config import (
    S3ServiceHealth,
)
from aiobotocore.session import get_session
from aiobotocore.config import AioConfig
from firecrest.dependencies import (
    DataTransferDependency,
)
from firecrest.status.health_check.checks.health_check_base import HealthCheckBase
from firecrest.plugins import settings


class S3HealthCheck(HealthCheckBase):

    def __init__(self, timeout: int):
        super().__init__()
        self.timeout = timeout

    def _get_s3_client(self, endpoint_url):
        return get_session().create_client(
            "s3",
            region_name=settings.data_operation.data_transfer.region,
            aws_secret_access_key=settings.data_operation.data_transfer.secret_access_key.get_secret_value(),
            aws_access_key_id=settings.data_operation.data_transfer.access_key_id.get_secret_value(),
            endpoint_url=endpoint_url,
            config=AioConfig(signature_version="s3v4"),
        )

    async def execute_check(self) -> S3ServiceHealth:

        health = S3ServiceHealth(service_type="s3")
        health.healthy = True

        async with self._get_s3_client(
            settings.data_operation.data_transfer.private_url.get_secret_value()
        ) as s3_client:
            paginator = s3_client.get_paginator("list_buckets")
            iterator = paginator.paginate(PaginationConfig={"MaxItems": 1})
            async for _page in iterator:
                pass

        return health

    async def handle_error(self, ex: Exception) -> S3ServiceHealth:
        health = S3ServiceHealth(service_type="s3")
        health.healthy = False
        health.message = str(ex)
        return health
