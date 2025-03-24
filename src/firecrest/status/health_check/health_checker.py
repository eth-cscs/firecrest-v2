# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import time


from firecrest.config import HPCCluster, HealthCheckException

from firecrest.status.health_check.checks.health_check_filesystem import (
    FilesystemHealthCheck,
)
from firecrest.status.health_check.checks.health_check_s3 import S3HealthCheck
from firecrest.status.health_check.checks.health_check_scheduler import (
    SchedulerHealthCheck,
)
from firecrest.status.health_check.checks.health_check_ssh import (
    SSHHealthCheck,
)
from lib.auth.authN.OIDC_token_auth import OIDCTokenAuth
from lib.scheduler_clients.scheduler_base_client import SchedulerBaseClient
from authlib.integrations.httpx_client import AsyncOAuth2Client
from firecrest.plugins import settings


class SchedulerHealthChecker:

    scheduler_client: SchedulerBaseClient = None
    cluster: HPCCluster = None
    token_decoder: OIDCTokenAuth = None

    def __init__(self, cluster: HPCCluster, token_decoder: OIDCTokenAuth = None):
        self.cluster = cluster
        if token_decoder is None:
            self.token_decoder = OIDCTokenAuth(
                settings.auth.authentication.public_certs
            )
        else:
            self.token_decoder = token_decoder

    async def check(self) -> None:
        try:
            client = AsyncOAuth2Client(
                self.cluster.service_account.client_id,
                self.cluster.service_account.secret.get_secret_value(),
            )

            token = await client.fetch_token(
                url=settings.auth.authentication.token_url,
                grant_type="client_credentials",
            )
            auth = self.token_decoder.auth_from_token(token["access_token"])
            checks = []
            sechedulerCheck = SchedulerHealthCheck(
                system=self.cluster,
                auth=auth,
                token=token,
                timeout=self.cluster.probing.timeout,
            )
            checks += [sechedulerCheck.check()]
            sshCheck = SSHHealthCheck(
                system=self.cluster,
                auth=auth,
                token=token,
                timeout=self.cluster.probing.timeout,
            )
            checks += [sshCheck.check()]

            for filesystem in self.cluster.file_systems:
                filesystemCheck = FilesystemHealthCheck(
                    system=self.cluster,
                    auth=auth,
                    token=token,
                    path=filesystem.path,
                    timeout=self.cluster.probing.timeout,
                )
                checks += [filesystemCheck.check()]

            if settings.storage and settings.storage.probing:
                s3Check = S3HealthCheck(
                    system=self.cluster, timeout=settings.storage.probing.timeout
                )
                checks += [s3Check.check()]

            results = await asyncio.gather(*checks, return_exceptions=True)
            self.cluster.servicesHealth = results
        except Exception as ex:
            error_message = f"{ex.__class__.__name__}"
            if len(str(ex)) > 0:
                error_message = f"{ex.__class__.__name__}: {str(ex)}"
            exception = HealthCheckException(service_type="exception")
            exception.healthy = False
            exception.last_checked = time.time()
            exception.message = error_message
            self.cluster.servicesHealth = [exception]
