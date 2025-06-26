# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


class SchedulerError(Exception):
    error_msg: str

    def __init__(self, error):
        super().__init__(error)
        self.error_msg = error


class SlurmError(SchedulerError):
    pass


class SlurmAuthTokenError(SlurmError):
    pass


class PbsError(SchedulerError):
    """Exception raised for errors related to the PBS scheduler."""

    pass


class SSHServiceError(Exception):
    pass


class SSHCredentials(Exception):
    pass
