# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandErrorHandling,
)
from firecrest.filesystem.ops.commands.ls_base_command import LsBaseCommand

UTILITIES_TIMEOUT = 5


class ChmodCommand(LsBaseCommand, BaseCommandErrorHandling):

    def __init__(self, target_path: str = None, mode: str = None) -> None:
        super().__init__(target_path, no_recursion=True)
        self.target_path = target_path
        self.mode = mode

    def get_log(self) -> str:
        return "chmod"

    def get_command(self) -> str:
        ls_command = super().get_command()
        return f"timeout {UTILITIES_TIMEOUT} chmod -v '{self.mode}' -- '{self.target_path}' && {ls_command}"

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):

        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        return super().parse_output(stdout, stderr, exit_status)
