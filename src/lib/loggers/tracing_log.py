# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
import re
import logging

from functools import wraps
from fastapi import Request
from starlette_context import context

# The actual tracing logger
tracing_logger = logging.getLogger("f7t_v2_tracing_log")


# Wrapper
def tracing_log_method(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if tracing_logger is None:
            return
        else:
            func(*args, **kwargs)

    return wrapper


# Put key-vale pair into context data map
def set_tracing_data(key: str, value: str) -> None:
    if context.exists():
        context[key] = value


# Retrieve value from context data map, return empty string if key does not exist
def get_tracing_data(key: str) -> str:
    if key in context:
        return context[key]
    return ""


# Get detailed backend logging dict
def get_tracing_backend_log() -> dict:
    if "backend" in context:
        return json.loads(get_tracing_data("backend"))
    else:
        return None


# Set command and exit status into context data map
def log_backend_command(command: str, exit_status: int) -> None:
    set_tracing_data(
        "backend", json.dumps({"command": command, "exit_status": str(exit_status)})
    )


# Set url and response status into context data map
def log_backend_http_scheduler(url: str, response_status: int) -> None:
    set_tracing_data(
        "backend", json.dumps({"url": url, "response_status": str(response_status)})
    )


@tracing_log_method
def tracing_log_middleware(request: Request, username: str, status_code: int) -> None:
    # Get URL
    url_path = request.scope["path"]
    root_path = request.scope["root_path"]
    # Normalize endpoint: remove prefix from root path, added by any API gateway
    endpoint = url_path.removeprefix(root_path) if root_path != "" else url_path
    # Initialize logging data
    resource = ""
    system_name = ""
    # Extract data from endpoint format "/resource/system/..."
    if match := re.search(r"^\/([^\/\s]+)\/([^\/\s]+)\/(.*)$", endpoint, re.IGNORECASE):
        resource = match.group(1)
        system_name = match.group(2)
    # Extract data from endpoint format "/resource/..."
    elif match := re.search(r"^\/([^\/\s]+)\/(.*)$", endpoint, re.IGNORECASE):
        resource = match.group(1)

    # Compose logging data packet
    log_data = {}
    log_data["username"] = username
    if system_name != "":
        log_data["system_name"] = system_name
    log_data["endpoint"] = endpoint
    log_data["resource"] = resource
    log_data["status_code"] = status_code
    log_data["user_agent"] = request.headers["user-agent"]
    # Get backend log if any
    backend = get_tracing_backend_log()
    if backend is not None:
        log_data["backend"] = backend
    # Write log
    tracing_logger.info(log_data)
