# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands


from firecrest.filesystem.ops.commands.base_command_with_timeout import (
    BaseCommandWithTimeout,
)


SIZE_LIMIT = 5 * 1024 * 1024


class ViewCommand(BaseCommandWithTimeout):

    def __init__(self, target_path: str = None) -> None:
        super().__init__()
        self.target_path = target_path

    def get_command(self) -> str:
        return (
            f"{super().get_command()} head --bytes {SIZE_LIMIT} -- '{self.target_path}'"
        )

    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        return stdout
