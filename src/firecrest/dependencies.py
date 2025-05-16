# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
from enum import Enum
from fastapi import Request, status, HTTPException
from aiobotocore.config import AioConfig
from aiobotocore.session import get_session
from botocore.handlers import validate_bucket_name

# extensions
from firecrest.config import (
    HPCCluster,
    HealthCheckType,
    SSHKeysService,
    SchedulerType,
)
from firecrest.filesystem.models import FilesystemRequestBase
from firecrest.plugins import settings

# dependencies
from lib.auth.authN.OIDC_token_auth import OIDCTokenAuth
from lib.auth.authN.authentication_service import AuthenticationService
from lib.auth.authZ.open_fga_client import OpenFGAClient
from lib.auth.authZ.authorization_service import AuthorizationService
from lib.dependencies import AuthDependency

# clients
from lib.ssh_clients.ssh_client import SSHClientPool
from lib.helpers.api_auth_helper import ApiAuthHelper
from lib.scheduler_clients.slurm.slurm_client import SlurmClient
from lib.ssh_clients.ssh_keygen_client import SSHKeygenClient
from lib.ssh_clients.ssh_static_keys_provider import SSHStaticKeysProvider

from fastapi.security import HTTPBearer
from fastapi import Depends


class APIAuthDependency(AuthDependency):

    globalAuthN: AuthenticationService
    globalAuthZ: AuthorizationService

    def __init__(self, authorize: bool = False) -> None:

        # Init sigleton authN services
        if not hasattr(APIAuthDependency, "globalAuthN"):
            APIAuthDependency.globalAuthN = OIDCTokenAuth(
                public_certs=settings.auth.authentication.public_certs
            )

        # Init sigleton authZ services
        if not hasattr(APIAuthDependency, "globalAuthZ"):
            if settings.auth.authorization:
                APIAuthDependency.globalAuthZ = OpenFGAClient(
                    url=settings.auth.authorization.url,
                    timeout=settings.auth.authorization.timeout,
                    max_connections=settings.auth.authorization.max_connections,
                )
            else:
                APIAuthDependency.globalAuthZ = None

        super().__init__(
            authNService=APIAuthDependency.globalAuthN,
            authZService=APIAuthDependency.globalAuthZ if authorize else None,
            token_url=settings.auth.authentication.token_url,
            scopes=settings.auth.authentication.scopes,
        )

    async def __call__(
        self,
        request: Request,
        _api_key=Depends(HTTPBearer()),
    ):
        system_name: str = None
        if "system_name" in request.path_params:
            system_name = request.path_params["system_name"]

        auth, token = await super().__call__(system_name, request)
        # TODO: rename ApiAuthHelper to something like Session Auth Helper
        ApiAuthHelper.set_auth(auth=auth)
        ApiAuthHelper.set_access_token(access_token=token)
        request.state.username = auth.username


class ServiceAvailabilityDependency:
    def __init__(self, service_type: HealthCheckType, ignore_health: bool = False):
        self.ignore_health = ignore_health
        self.service_type = service_type

    def __file_system_health(self, system: HPCCluster, request: Request):
        path: str = request.query_params.get("path")
        # if path is not defined as a query param extract it from the request body
        if path is None:
            try:
                json = asyncio.run(request.json())
                path = FilesystemRequestBase(**json).path
            except Exception:
                pass

        if path is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All filesystem requests require a path or source_path parameter.",
            )
        service = None
        if system.servicesHealth:
            service = next(
                filter(
                    lambda service: service.service_type == self.service_type
                    and path.startswith(service.path),
                    system.servicesHealth,
                ),
                None,
            )
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail=f"No filesystem health checker serving the request path was found on {system.name}.",
            )
        if not service.healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"The requested filesystem ({service.path} on {system.name}) is unhealthy.",
            )

    def __scheduler_health(self, system: HPCCluster):
        service = None
        if system.servicesHealth:
            service = next(
                filter(
                    lambda service: service.service_type == self.service_type,
                    system.servicesHealth,
                ),
                None,
            )
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail=f"No scheduler health checker for the requested system ({system.name}) was found.",
            )
        if not service.healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"The scheduler service for the requested system ({system.name}) is unhealthy.",
            )

    def __ssh_health(self, system: HPCCluster):
        service = None
        if system.servicesHealth:
            service = next(
                filter(
                    lambda service: service.service_type == self.service_type,
                    system.servicesHealth,
                ),
                None,
            )
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail=f"No ssh health checker for the requested system ({system.name}) was found.",
            )
        if not service.healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"The ssh service for the requested system ({system.name}) is unhealthy.",
            )

    def __call__(
        self,
        system_name: str,
        request: Request = None,
    ):
        try:
            system = next(
                filter(lambda cluster: cluster.name == system_name, settings.clusters)
            )
            # Check health of requested system
            if not self.ignore_health and system.probing:
                if self.service_type == HealthCheckType.filesystem:
                    self.__file_system_health(system, request)
                if self.service_type == HealthCheckType.scheduler:
                    self.__scheduler_health(system)
                if self.service_type == HealthCheckType.ssh:
                    self.__ssh_health(system)

            return system
        except StopIteration as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="System not found"
            ) from exc

    # To allow for dependency override eq checks for class equality
    def __eq__(self, other):
        if isinstance(other, ServiceAvailabilityDependency):
            return (
                self.ignore_health == other.ignore_health
                and self.service_type == other.service_type
            )
        return False

    # To allow for dependency override hash is based on class
    def __hash__(self):
        return hash(ServiceAvailabilityDependency.__class__)


class SSHClientDependency:

    client_pools: SSHClientPool = {}
    lock = asyncio.Lock()

    def __init__(
        self,
        ignore_health: bool = False,
    ):
        self.ignore_health = ignore_health
        if isinstance(settings.ssh_credentials, SSHKeysService):
            self.key_provider = SSHKeygenClient(
                settings.ssh_credentials.url,
                settings.ssh_credentials.max_connections,
            )
        elif isinstance(settings.ssh_credentials, dict):
            self.key_provider = SSHStaticKeysProvider(settings.ssh_credentials)
        else:
            raise TypeError("Unsupported SSHKeysProvider")

    async def __call__(self, system_name: str):
        system = ServiceAvailabilityDependency(
            service_type=HealthCheckType.ssh, ignore_health=self.ignore_health
        )(system_name=system_name)

        async with SSHClientDependency.lock:
            if system_name in SSHClientDependency.client_pools:
                return SSHClientDependency.client_pools[system_name]

            client_pool = SSHClientPool(
                host=system.ssh.host,
                port=system.ssh.port,
                proxy_host=system.ssh.proxy_host,
                proxy_port=system.ssh.proxy_port,
                key_provider=self.key_provider,
                connect_timeout=system.ssh.timeout.connection,
                login_timeout=system.ssh.timeout.login,
                execute_timeout=system.ssh.timeout.command_execution,
                idle_timeout=system.ssh.timeout.idle_timeout,
                max_clients=system.ssh.max_clients,
                keep_alive=system.ssh.timeout.keep_alive,
            )
            SSHClientDependency.client_pools[system_name] = client_pool
            return client_pool

    # To allow for dependency override eq checks for class equality
    def __eq__(self, other):
        if isinstance(other, SSHClientDependency):
            return self.ignore_health == other.ignore_health
        return False

    # To allow for dependency override hash is based on class
    def __hash__(self):
        return hash(SSHClientDependency.__class__)

    @classmethod
    def prune_client_pools(self):
        for client_pool in SSHClientDependency.client_pools.values():
            client_pool.prune_connection_pool()


class SchedulerClientDependency:
    def __init__(self, ignore_health: bool = False):
        self.ignore_health = ignore_health

    # Note: this fuction allows for unit test client injection override
    async def _get_ssh_client(self, system_name):
        return await SSHClientDependency(ignore_health=self.ignore_health)(
            system_name=system_name
        )

    async def __call__(
        self,
        system_name: str,
    ):
        system = ServiceAvailabilityDependency(
            service_type=HealthCheckType.scheduler, ignore_health=self.ignore_health
        )(system_name=system_name)
        match system.scheduler.type:
            case SchedulerType.slurm:
                return SlurmClient(
                    await self._get_ssh_client(system_name),
                    system.scheduler.version,
                    system.scheduler.api_version,
                    system.scheduler.api_url,
                    system.scheduler.timeout)
            case _:
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="The requested scheduler type is not implemented",
                )

    # To allow for dependency override eq checks for class equality
    def __eq__(self, other):
        if isinstance(other, SchedulerClientDependency):
            return self.ignore_health == other.ignore_health
        return False

    # To allow for dependency override hash is based on class
    def __hash__(self):
        return hash(SchedulerClientDependency.__class__)


class S3ClientConnectionType(str, Enum):
    private = "private"
    public = "public"


class S3ClientDependency:
    def __init__(
        self, connection: S3ClientConnectionType = S3ClientConnectionType.public
    ):
        if settings.storage:
            self.url = settings.storage.public_url
            if connection == S3ClientConnectionType.private:
                self.url = settings.storage.private_url

    async def __call__(self):
        async with get_session().create_client(
            "s3",
            region_name=settings.storage.region,
            aws_secret_access_key=settings.storage.secret_access_key.get_secret_value(),
            aws_access_key_id=settings.storage.access_key_id,
            endpoint_url=self.url,
            config=AioConfig(signature_version="s3v4"),
        ) as client:
            # This is required because botocore library bucket_name validation is not compliant
            # with ceph multi tenancy bucket names
            if settings.storage.tenant:
                client.meta.events.unregister(
                    "before-parameter-build.s3", validate_bucket_name
                )
            return client

    # To allow for dependency override eq checks for class equality
    def __eq__(self, other):
        if isinstance(other, S3ClientDependency):
            if hasattr(self, "url") and hasattr(other, "url"):
                return self.url == other.url
        return False

    # To allow for dependency override hash is based on class
    def __hash__(self):
        return hash(S3ClientDependency.__class__)
