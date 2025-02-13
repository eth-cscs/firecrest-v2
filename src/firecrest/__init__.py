# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import logging
import re
import types
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from starlette.exceptions import HTTPException as StarletteHTTPException

# configs
from firecrest import config
from firecrest.plugins import settings as plugin_settings

# request vars
from lib import request_vars

# helpers
from lib.handlers.api_response_handler import (
    response_error_handler,
    meta_headers_handler,
)
from lib.ssh_clients.ssh_keygen_client import SSHKeygenClient
from firecrest.dependencies import SSHClientDependency
from firecrest.status.health_check.health_checker import (
    SchedulerHealthChecker,
)

# routers
from firecrest.status.router import (
    router as status_router,
    router_on_systen as status_system_router,
)
from firecrest.compute.router import router as compute_router
from firecrest.filesystem.router import router as filesystem_router
from lib.scheduler_clients import SlurmRestClient

from apscheduler import AsyncScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.datastores.memory import MemoryDataStore
from apscheduler.eventbrokers.local import LocalEventBroker


logger = logging.getLogger(__name__)


def create_app(settings: config.Settings) -> FastAPI:
    # Register trackers
    register_errors_reporting()
    # Instance app

    app = FastAPI(
        title="FirecREST",
        version=settings.app_version,
        servers=settings.doc_servers,
        debug=settings.app_debug,
        root_path=settings.apis_root_path,
        root_path_in_servers=not settings.doc_servers,
        lifespan=lifespan,
        # middleware=middleware,
    )
    # Register middlewares
    register_middlewares(app=app)
    # Register routes
    register_routes(app=app, settings=settings)
    # Register exception handlers
    register_exception_handlers(app=app)

    return app


@asynccontextmanager
async def lifespan(app: FastAPI):

    data_store = MemoryDataStore()
    event_broker = LocalEventBroker()

    app.state.scheduler = AsyncScheduler(data_store, event_broker)

    # Init Slurm REST Client
    await SlurmRestClient.get_aiohttp_client()
    await SSHKeygenClient.get_aiohttp_client()
    async with app.state.scheduler as scheduler:
        await schedule_tasks(scheduler)
        await scheduler.start_in_background()
        yield
        await scheduler.stop()
    # Clean up Slurm REST Client
    await SlurmRestClient.close_aiohttp_client()
    await SSHKeygenClient.close_aiohttp_client()


def register_errors_reporting():
    # ***SENTRY_INTEGRATION***
    pass


async def schedule_tasks(scheduler: AsyncScheduler):
    for cluster in plugin_settings.clusters:
        await scheduler.add_schedule(
            SchedulerHealthChecker(cluster).check,
            IntervalTrigger(seconds=cluster.probing.interval),
            id=f"check-cluster-{cluster.name}",
        )
    await scheduler.add_schedule(
        SSHClientDependency.prune_client_pools,
        IntervalTrigger(seconds=5),
        id="prune-connection-pool",
    )


def register_middlewares(app: FastAPI):
    @app.middleware("http")
    async def init_request_vars(request: Request, call_next):
        initial_g = types.SimpleNamespace()
        request_vars.request_global.set(initial_g)
        response = await call_next(request)
        return response

    @app.middleware("http")
    async def init_response_headers(request: Request, call_next):
        return await meta_headers_handler(request=request, call_next=call_next)

    @app.middleware("http")
    async def log_middleware(request: Request, call_next):
        try:
            response = await call_next(request)
            username = None
            if hasattr(request.state, "username"):
                username = request.state.username

            system_name = None
            # /filesystem/{system_name}/.*
            # /compute/{system_name}/.*
            # /status/{system_name}
            if match := re.search(
                r"^\/(?:compute|filesystem|status)\/([^\/\s]+)\/.*$",
                request.url.path,
                re.IGNORECASE,
            ):
                system_name = match.group(1)

            logger.info(
                {
                    "username": username,
                    "system": system_name,
                    "endpoint": request.url.path,
                    "satus_code": response.status_code,
                }
            )
            return response
        except Exception as e:
            logger.error(
                {
                    "endpoint": request.url.path,
                    "error": str(e),
                }
            )
            raise e


def register_routes(app: FastAPI, settings: config.Settings):
    app.include_router(status_router)
    app.include_router(status_system_router)
    app.include_router(compute_router)
    app.include_router(filesystem_router)


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(Exception)
    @app.exception_handler(StarletteHTTPException)
    @app.exception_handler(RequestValidationError)
    async def http_exception_handler(request, exc):
        return response_error_handler(
            exc=exc,
            request=request,
        )
