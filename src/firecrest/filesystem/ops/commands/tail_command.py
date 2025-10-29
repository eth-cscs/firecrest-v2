# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from firecrest.filesystem.ops.commands.base_command_with_timeout import (
    BaseCommandWithTimeout,
)


class TailCommand(BaseCommandWithTimeout):

    def __init__(
        self,
        target_path: str | None = None,
        file_bytes: str | None = None,
        lines: str | None = None,
        skip_heading: bool = False,
        command_timeout: int = 5
    ) -> None:
        super().__init__(command_timeout=command_timeout)
        self.target_path = target_path
        self.file_bytes = file_bytes
        self.lines = lines
        self.skip_heading = skip_heading

    def get_command(
        self,
    ) -> str:
        options = ""
        if self.file_bytes:
            if self.skip_heading:
                options += f"--bytes='+{self.file_bytes}' "
            else:
                options += f"--bytes='{self.file_bytes}' "

        if self.lines:
            if self.skip_heading:
                options += f"--lines='+{self.lines}' "
            else:
                options += f"--lines='{self.lines}' "

        return f"{super().get_command()} tail {options}-- '{self.target_path}'"

    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        return stdout
