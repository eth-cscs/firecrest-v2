# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandWithTimeoutErrorHandling,
)
from lib.ssh_clients.ssh_client import BaseCommand

UTILITIES_TIMEOUT = 5


class RmCommand(BaseCommand, BaseCommandWithTimeoutErrorHandling):

    def __init__(self, target_path: str = None) -> None:
        super().__init__()
        self.target_path = target_path

    def get_command(self) -> str:
        return f"timeout {UTILITIES_TIMEOUT} rm -r --interactive=never -- '{self.target_path}'"

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)
