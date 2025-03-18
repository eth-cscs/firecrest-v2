# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from firecrest.filesystem.ops.commands.base_command_with_timeout import (
    BaseCommandWithTimeout,
)
from firecrest.filesystem.ops.commands.ls_base_command import LsBaseCommand


class ChownCommand(BaseCommandWithTimeout):

    def __init__(
        self, target_path: str = None, owner: str = None, group: str = None
    ) -> None:
        self.target_path = target_path
        self.owner = owner
        self.group = group
        self.ls_command = LsBaseCommand(target_path, no_recursion=True)

    def get_command(self) -> str:

        return f"{super().get_command()} chown -v '{self.owner}':'{self.group}' -- '{self.target_path}' && {self.ls_command.get_command()}"

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        return self.ls_command.parse_output(stdout, stderr, exit_status)
