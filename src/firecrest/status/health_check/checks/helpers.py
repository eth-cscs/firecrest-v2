# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import logging
from firecrest.config import BackendServiceType

logger = logging.getLogger("uvicorn.error")


def log_health_check_error(service_type: BackendServiceType,
                           health_message: str,
                           exception: Exception,
                           system_name: str | None = None,
                           filesystem_path: str | None = None,
                           username: str | None = None):

    log_data = {}

    message = ""
    if service_type == BackendServiceType.filesystem:
        message = (
            f"Health check for {service_type.value} service on "
            f"{system_name} at path {filesystem_path} failed: {health_message}"
        )
        log_data["firecrest.username"] = username
    elif service_type == BackendServiceType.external_storage:
        message = f"Health check for {service_type.value} failed: {health_message}"
    else:
        message = (
            f"Health check for {service_type.value} service on "
            f"{system_name} failed: {health_message}"
        )
        log_data["firecrest.username"] = username

    log_data["message"] = message
    log_data["error.type"] = exception.__class__.__name__
    log_data["error.message"] = f"{exception.__class__.__name__}: {health_message}"

    logger.error(log_data)
