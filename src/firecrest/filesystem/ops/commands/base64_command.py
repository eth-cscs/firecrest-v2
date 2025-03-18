# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


from firecrest.filesystem.ops.commands.base_command_with_timeout import (
    BaseCommandWithTimeout,
)


class Base64Command(BaseCommandWithTimeout):

    def __init__(self, path: str | None = None, decode: bool = False) -> None:
        super().__init__()
        self.path = path
        self.decode = decode

    def get_command(
        self,
    ) -> str:
        if self.decode:
            return f"{super().get_command()} base64 -d > '{self.path}'"
        return f"{super().get_command()} base64 --wrap=0 -- '{self.path}'"

    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        return stdout
