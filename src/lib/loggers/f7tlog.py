# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import logging

f7tlogger = logging.getLogger("f7t_v2_log")


def init_f7tlog(log_level: int):
    f7tlogger.setLevel(log_level)


def init_f7tlog_string(log_level: str):
    try:
        level = logging._nameToLevel[log_level]
        f7tlogger.setLevel(level)
    except KeyError:
        f7tlogger.warning(f"Log level {log_level} not found.")


def f7tlog_set_level(level: int = 0) -> None:
    if level == 0:
        f7tlogger.warning(f"Log level not updated.")
        return
    if level in [
        logging.CRITICAL,
        logging.ERROR,
        logging.WARNING,
        logging.INFO,
        logging.DEBUG,
    ]:
        f7tlogger.setLevel(level)
    else:
        f7tlogger.error(f"Log level to set {level} is not valid.")
