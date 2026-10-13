# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import logging
from firecrest.config import BackendServiceType


def log_health_check_error(service_type: BackendServiceType,
                           health_message: str,
                           system_name: str = None,
                           filesystem_path: str = None,
                           exception: Exception = None,
                           username: str = None):

    logger = logging.getLogger("uvicorn.error")
    log_data = {}

    log_data["message"] = (
        f"Health check for {service_type.value} service on {system_name} failed: {health_message}" if
        service_type != BackendServiceType.filesystem else
        f"Health check for {service_type.value} service on {system_name} at path {filesystem_path} failed: {health_message}"
    )

    log_data["error.type"] = exception.__class__.__name__ if exception else f"Unknown{service_type.value}Exception"
    if exception:
        log_data["error.message"] = (
            exception.__class__.__name__ + ": " + health_message
        )
    else:
        log_data["error.message"] = f"Unknown {service_type.value} exception"

    log_data["firecrest.username"] = username

    logger.error(log_data)
