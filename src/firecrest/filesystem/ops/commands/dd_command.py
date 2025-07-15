# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands

from firecrest.plugins import settings

from firecrest.filesystem.ops.commands.base_command_with_timeout import (
    BaseCommandWithTimeout,
)


OPS_SIZE_LIMIT = settings.storage.max_ops_file_size


class DdCommand(BaseCommandWithTimeout):

    def __init__(self, target_path: str = None, size: int = None,
                 offset: int = 0) -> None:
        super().__init__()

        self.target_path = target_path
        self.size = OPS_SIZE_LIMIT if (size is None or size > OPS_SIZE_LIMIT) else size
        self.count = 1
        self.offset = offset

        if offset is None:
            self.skip = 0
            self.offset = 0
        elif offset % self.size == 0:
            self.skip = offset // self.size
        else:
            self.count = 2
            self.skip = offset // self.size

    def get_command(self) -> str:
        print(f"dd if='{self.target_path}' bs={self.size} skip={self.skip} count={self.count}")
        return (
            f"{super().get_command()} dd if='{self.target_path}' bs={self.size} skip={self.skip} count={self.count}"
        )

    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        i = 0
        if self.count == 2:
            i = self.offset % self.size

        return stdout[i:i+self.size]
