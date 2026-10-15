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

    match service_type.value:
        case BackendServiceType.filesystem:
            log_data["error.path"] = filesystem_path
            log_data["error.system"] = system_name
            log_data["firecrest.username"] = username
        case BackendServiceType.scheduler:
            log_data["error.system"] = system_name
            log_data["firecrest.username"] = username
        case BackendServiceType.ssh:
            log_data["error.system"] = system_name
            log_data["firecrest.username"] = username
        case BackendServiceType.external_storage:
            pass
        case _:
            pass

    log_data["message"] = "Health check failed"
    log_data["error.service"] = service_type.value
    log_data["error.type"] = exception.__class__.__name__
    log_data["error.message"] = (
        f"{exception.__class__.__name__}: {health_message}"
    )

    logger.error(log_data)
