# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands

from firecrest.filesystem.ops.commands.base_command_with_timeout import (
    BaseCommandWithTimeout,
)


class DdCommand(BaseCommandWithTimeout):

    def __init__(
        self,
        target_path: str = None,
        size: int = None,
        offset: int = 0,
        size_limit: int = None,
        command_timeout: int = 5,
    ) -> None:
        super().__init__(command_timeout=command_timeout)

        self.target_path = target_path
        self.size = size_limit if (size is None or size > size_limit) else size
        self.offset = offset

        if offset is None:
            self.skip = 0
            self.offset = 0
        else:
            self.skip = offset // self.size

    def get_command(self) -> str:
        # `count = 2` to bring back 2 chunks of the file, in case the offset is not a multiple of `size`
        # After, the `stdout` is processed on the `parse_output` method to return the requested chunk
        # This increases efficiency by not bringing back `bs` of size 1B which leads to multiple reads (`count=N`) on the system
        return f"{super().get_command()} dd if='{self.target_path}' bs={self.size} skip={self.skip} count=2"

    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        i = self.offset % self.size
        return stdout[i : i + self.size]
