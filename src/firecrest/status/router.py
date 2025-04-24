# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Path, status
from typing import Annotated, Any

# configs
from firecrest.config import HPCCluster, HealthCheckType
from firecrest.status.commands.id_command import IdCommand
from firecrest.plugins import settings

# helpers
from lib.helpers.api_auth_helper import ApiAuthHelper
from lib.helpers.router_helper import create_router

# dependencies
from firecrest.dependencies import (
    APIAuthDependency,
    SSHClientDependency,
    SchedulerClientDependency,
    ServiceAvailabilityDependency,
)

# models
from lib.scheduler_clients.scheduler_base_client import SchedulerBaseClient
from firecrest.status.models import (
    GetLiveness,
    GetPartitionsResponse,
    GetReservationsResponse,
    GetSystemsResponse,
    UserInfoResponse,
)
from firecrest.status.models import GetNodesResponse
from lib.ssh_clients.ssh_client import SSHClient

router = create_router(
    prefix="/status",
    tags=["status"],
    dependencies=[Depends(APIAuthDependency(authorize=False))],
)

router_on_systen = create_router(
    prefix="/status/{system_name}",
    tags=["status"],
    dependencies=[Depends(APIAuthDependency(authorize=True))],
)

router_liveness = create_router(
    prefix="/status/liveness",
    tags=["status"],
)


@router.get(
    "/systems",
    description="Get the list of systems and health status",
    status_code=status.HTTP_200_OK,
    response_model=GetSystemsResponse,
    response_description="System list returned successfully",
)
async def get_systems() -> Any:
    return {"systems": settings.clusters}


@router_on_systen.get(
    "/nodes",
    description="Get the list of nodes of a `{system_name}`",
    status_code=status.HTTP_200_OK,
    response_model=GetNodesResponse,
    response_description="Nodes list returned successfully",
)
async def get_system_nodes(
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency(ignore_health=True)),
    ] = None,
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    try:
        nodes = await scheduler_client.get_nodes(
            username=username, jwt_token=access_token
        )
        if nodes is None or len(nodes) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No nodes found"
            )
        return {"nodes": nodes}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@router_on_systen.get(
    "/reservations",
    description="Get the list of reservations of a `{system_name}`",
    status_code=status.HTTP_200_OK,
    response_model=GetReservationsResponse,
    response_description="Reservations list returned successfully",
)
async def get_system_reservations(
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency(ignore_health=True)),
    ] = None,
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    try:
        reservations = await scheduler_client.get_reservations(
            username=username, jwt_token=access_token
        )
        return {"reservations": reservations}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@router_on_systen.get(
    "/partitions",
    description="Get the list of partitions of a `{system_name}`",
    status_code=status.HTTP_200_OK,
    response_model=GetPartitionsResponse,
    response_description="Partitions list returned successfully",
)
async def get_system_partitions(
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency(ignore_health=True)),
    ] = None,
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    try:
        partitions = await scheduler_client.get_partitions(
            username=username, jwt_token=access_token
        )
        return {"partitions": partitions}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@router_on_systen.get(
    "/userinfo",
    description="Get current user information on a `{system_name}`",
    status_code=status.HTTP_200_OK,
    response_model=UserInfoResponse,
    response_description="User information returned successfully",
)
async def get_userinfo(
    ssh_client: Annotated[
        SSHClient,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.ssh),
        use_cache=False,
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    id = IdCommand()
    async with ssh_client.get_client(username, access_token) as (client):
        output = await client.execute(id)
        return output


@router_liveness.get(
    "/",
    description="Get liveness status of FirecREST",
    status_code=status.HTTP_200_OK,
    response_model=GetLiveness,
    response_description="Liveness status returned successfully",
)
async def get_liveness() -> Any:

    oldest_check = -1
    healthcheck_runs = {}

    # if not clusters are configured the health checker is not running
    if len(settings.clusters) == 0:
        oldest_check = 0

    for cluster in settings.clusters:
        if cluster.servicesHealth and len(cluster.servicesHealth) > 0:
            timestamp = cluster.servicesHealth[0].last_checked
            time_difference = (datetime.now(timezone.utc) - timestamp).seconds
            if time_difference > oldest_check:
                oldest_check = time_difference
            healthcheck_runs[cluster.name] = cluster.servicesHealth[0].last_checked

    return {"healthcheck_runs": healthcheck_runs, "last_update": oldest_check}
