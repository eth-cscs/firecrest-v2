# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import uvicorn


# plugins
from firecrest.plugins import settings


import logging
import types
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from starlette.exceptions import HTTPException as StarletteHTTPException
from firecrest.status.health_check.health_checker_cluster import ClusterHealthChecker
from firecrest.status.health_check.health_checker_storage import StorageHealthChecker
from starlette_context import plugins
from starlette_context.middleware import RawContextMiddleware

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

# routers
from firecrest.status.router import (
    router as status_router,
    router_on_systen as status_system_router,
    router_liveness as status_liveness_router,
)
from firecrest.compute.router import router as compute_router
from firecrest.filesystem.router import router as filesystem_router
from lib.scheduler_clients import SlurmRestClient

from apscheduler import AsyncScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.datastores.memory import MemoryDataStore
from apscheduler.eventbrokers.local import LocalEventBroker

# FirecREST tracing JSON logger
from lib.loggers.tracing_log import tracing_log_middleware

# Uvicorn logger
logger = logging.getLogger(__name__)


def create_app(settings: config.Settings) -> FastAPI:

    # Instance app
    app = FastAPI(
        title="FirecREST",
        version=settings.app_version,
        servers=settings.doc_servers,
        debug=settings.app_debug,
        root_path=settings.apis_root_path,
        root_path_in_servers=not settings.doc_servers,
        lifespan=lifespan,
    )
    # Register middlewares
    register_middlewares(app=app)
    # Register routes
    register_routes(app=app, settings=settings)
    # Register exception handlers
    register_exception_handlers(app=app)

    app.add_middleware(
        RawContextMiddleware,
        plugins=(plugins.RequestIdPlugin(), plugins.CorrelationIdPlugin()),
    )
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


async def schedule_tasks(scheduler: AsyncScheduler):
    for cluster in plugin_settings.clusters:
        if cluster.probing:
            await scheduler.add_schedule(
                ClusterHealthChecker(cluster).check,
                IntervalTrigger(seconds=cluster.probing.interval),
                id=f"check-cluster-{cluster.name}",
            )
    if settings.storage and settings.storage.probing:
        await scheduler.add_schedule(
            StorageHealthChecker(settings.storage).check,
            IntervalTrigger(seconds=settings.storage.probing.interval),
            id="check-storage",
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
            # Logging from Middleware
            if settings.logger.enable_tracing_log:
                tracing_log_middleware(request, username, response.status_code)
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
    app.include_router(status_liveness_router)
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


app = create_app(settings=settings)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=True)
