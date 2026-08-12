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
from lib.exceptions import (
    SSHServiceError,
    SchedulerError,
)
from lib.ssh_clients.ssh_client import SSHClientError
from firecrest.status.health_check.health_checker_cluster import ClusterHealthChecker
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
from lib.ssh_clients.ssh_keygen_credentials_provider import SSHKeygenCredentialsProvider
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


from starlette_context import context
from starlette_context.header_keys import HeaderKeys

# FirecREST tracing JSON logger
from lib.loggers.tracing_log import Log_operation, tracing_log_middleware

# Uvicorn logger
logger = logging.getLogger(__name__)


class EndpointFilter(logging.Filter):
    """Drops noisy /status/liveness access logs and lifts the HTTP method
    and status code out of uvicorn's free-text access log message into
    dedicated record fields, so the JSON formatter can emit them as their
    own (ECS-style) fields instead of only inside the message string."""

    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn.access records carry (client_addr, method, path, http_version,
        # status_code) as positional args - see uvicorn's h11/httptools protocols.
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client_addr, method, path, http_version, status_code = record.args
            if path.find("/status/liveness") != -1:
                return False
            record.http_request_method = method
            record.http_response_status_code = status_code
            return True
        return record.getMessage().find("/status/liveness") == -1


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
    await SSHKeygenCredentialsProvider.get_aiohttp_client()
    async with app.state.scheduler as scheduler:
        await schedule_tasks(scheduler)
        await scheduler.start_in_background()
        yield
        await scheduler.stop()
    # Clean up Slurm REST Client
    await SlurmRestClient.close_aiohttp_client()
    await SSHKeygenCredentialsProvider.close_aiohttp_client()


async def schedule_tasks(scheduler: AsyncScheduler):
    for cluster in plugin_settings.clusters:
        await scheduler.add_schedule(
            ClusterHealthChecker(cluster).check,
            IntervalTrigger(seconds=cluster.probing.interval_check),
            id=f"check-cluster-{cluster.name}",
        )
    await scheduler.add_schedule(
        SSHClientDependency.prune_client_pools,
        IntervalTrigger(seconds=5),
        id="prune-connection-pool",
    )


def register_middlewares(app: FastAPI):
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

    @app.middleware("http")
    async def init_request_vars(request: Request, call_next):
        # A fresh namespace per request, bound in this async context, so
        # per-request state (e.g. auth in api_auth_helper.py) never leaks
        # across concurrent requests sharing the contextvar's default.
        request_vars.request_global.set(types.SimpleNamespace())
        response = await call_next(request)
        return response

    @app.middleware("http")
    async def init_response_headers(request: Request, call_next):
        return await meta_headers_handler(request=request, call_next=call_next)

    @app.middleware("http")
    async def log_middleware(request: Request, call_next):
        try:
            # Logging from Middleware request
            if settings.logger.enable_tracing_log:
                tracing_log_middleware(
                    Log_operation.Request,
                    request,
                    None,
                    None,
                    settings.logger.loggable_request_headers,
                )

            response = await call_next(request)

            # Logging from Middleware response
            if settings.logger.enable_tracing_log:
                tracing_log_middleware(
                    Log_operation.Response,
                    request,
                    (
                        request.state.username
                        if hasattr(request.state, "username")
                        else None
                    ),
                    response.status_code,
                    settings.logger.loggable_request_headers,
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

    @app.middleware("http")
    async def lower_case_path(request: Request, call_next):

        path = request.scope["path"].lower()
        request.scope["path"] = path

        response = await call_next(request)
        return response


def register_routes(app: FastAPI, settings: config.Settings):
    app.include_router(status_router)
    app.include_router(status_system_router)
    app.include_router(status_liveness_router)
    app.include_router(compute_router)
    app.include_router(filesystem_router)


def register_exception_handlers(app: FastAPI):
    # Base classes must be listed explicitly: the `Exception` handler is served by
    # Starlette's ServerErrorMiddleware, which re-raises after responding. Only handlers
    # registered here are resolved (by MRO) without re-raising.
    @app.exception_handler(Exception)

    # Explicitly register base classes to avoid re-raising by Starlette's ServerErrorMiddleware
    @app.exception_handler(StarletteHTTPException)
    @app.exception_handler(RequestValidationError)
    @app.exception_handler(SchedulerError)
    @app.exception_handler(SSHServiceError)
    @app.exception_handler(SSHClientError)
    async def http_exception_handler(request, exc):

        def get_tracing_data(key: str) -> str:
            if key in context:
                return context[key]
            return ""

        cause_chain = [str(exc)]
        cause = exc.__cause__
        visited = set()
        while cause is not None:
            if id(cause) in visited:
                break
            visited.add(id(cause))
            cause_chain.append(str(cause))
            cause = cause.__cause__

        response = response_error_handler(
            exc=exc,
            request=request,
        )

        msg = "\n caused by: ".join(cause_chain)
        if context.exists():
            msg += "\n correlation_id: " + get_tracing_data(HeaderKeys.correlation_id)
            msg += "\n request_id: " + get_tracing_data(HeaderKeys.request_id)

        if response.status_code and response.status_code < 500:
            logging.getLogger("uvicorn.error").warning(msg)
        else:
            logging.getLogger("uvicorn.error").error(msg)

        return response


app = create_app(settings=settings)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=True)
