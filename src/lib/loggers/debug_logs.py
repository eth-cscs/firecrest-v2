# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import logging
import firecrest.plugins

debug_logger = logging.getLogger("f7t_v2_debug_log")

def debug_logger_set_level(level: int = 0) -> None:
    if level == 0:
        # Apply default
        debug_logger.setLevel(firecrest.plugins.settings.logs.debug_log_level)
    else:
        if level in [logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]:
            debug_logger.setLevel(level)
        else:
            debug_logger.error(f"Log level to set {level} is not valid.")
