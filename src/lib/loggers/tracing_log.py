# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
import logging

from functools import wraps
from fastapi import Request
from starlette_context import context


# The actual tracing logger
tracing_logger = logging.getLogger("f7t_v2_tracing_log")


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

# Set command exit status into context data map
def log_exit_status(exit_status: int) -> None:
    set_tracing_data("exit_status", str(exit_status))

@tracing_log_method
def tracing_log_middleware(request: Request, username: str, status_code: int) -> None:
    # Get action's exit status
    exit_status = get_tracing_data("exit_status")
    # Get URL
    url_path = request.scope["path"]
    root_path = request.scope["root_path"]
    # Normalize endpoint: remove prefix from root path, added by any API gateway
    endpoint = url_path.removeprefix(root_path) if root_path != "" else url_path
    # Initialize logging data
    group = ""
    resource = ""
    system_name = ""
    command = ""
    # Extract data from endpoint format "/resource/system/(group/command)"
    if match := re.search(
        r"^\/([^\/\s]+)\/([^\/\s]+)\/(.*)$",
        endpoint,
        re.IGNORECASE
    ):
        resource = match.group(1)
        system_name = match.group(2)
        # Get group and command
        tmp = match.group(3)
        if match_cmd := re.search(r"^([^\/\s]+)\/(.*)$", tmp, re.IGNORECASE):
            group = match_cmd.group(1)
            command = match_cmd.group(2)
        else:
            group = ""
            command = tmp
    # Extract data from endpoint format "/resource/command"
    elif match := re.search(
        r"^\/([^\/\s]+)\/(.*)$",
        endpoint,
        re.IGNORECASE):
        resource = match.group(1)
        command = match.group(2)
    # Compose logging data packet
    log_data = {}
    log_data["username"] = username
    log_data["system_name"] = system_name
    log_data["endpoint"] = endpoint
    log_data["status_code"] = status_code
    log_data["exit_status"] = exit_status
    log_data["resource"] = resource
    log_data["group"] = group
    log_data["command"] = command
    log_data["url_path"] = url_path
    log_data["user_agent"] = request.headers["user-agent"]
    # Write log
    tracing_logger.info(log_data)