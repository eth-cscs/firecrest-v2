# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandWithTimeoutErrorHandling,
)
from firecrest.filesystem.ops.commands.ls_base_command import LsBaseCommand


UTILITIES_TIMEOUT = 5


class SymlinkCommand(LsBaseCommand, BaseCommandWithTimeoutErrorHandling):

    def __init__(self, target_path: str = None, link_path: str = None) -> None:
        super().__init__(target_path, no_recursion=True)
        self.target_path = target_path
        self.link_path = link_path

    def get_command(self) -> str:
        ls_command = super().get_command()
        return f"timeout {UTILITIES_TIMEOUT} ln -s -- '{self.target_path}' '{self.link_path}' && {ls_command}"

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        return super().parse_output(stdout, stderr, exit_status)
