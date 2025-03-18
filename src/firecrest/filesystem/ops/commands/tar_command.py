# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum
import os

from firecrest.filesystem.ops.commands.base_command_with_timeout import (
    BaseCommandWithTimeout,
)


class TarCommand(BaseCommandWithTimeout):

    class Operation(str, Enum):
        compress = "compress"
        extract = "extract"

    def __init__(
        self,
        source_path: str,
        target_path: str,
        match_pattern: str = None,
        dereference: bool = False,
        operation: Operation = Operation.compress,
    ) -> None:
        super().__init__()
        self.target_path = target_path
        self.source_path = source_path
        self.match_pattern = match_pattern
        self.dereference = dereference
        self.operation = operation

    def get_command(
        self,
    ) -> str:

        match self.operation:
            case TarCommand.Operation.compress:
                return self.get_compress_command()
            case TarCommand.Operation.extract:
                return self.get_extract_command()

    def get_compress_command(self) -> str:
        options = ""
        if self.dereference:
            options += "--dereference"

        source_dir = os.path.dirname(self.source_path)
        source_file = os.path.basename(self.source_path)

        if self.match_pattern:
            return f"{super().get_command()} bash -c \"cd {source_dir}; {super().get_command()} find . -type f -regex '{self.match_pattern}' -print0 | tar {options} -czvf '{self.target_path}' --null --files-from - \""

        return f"{super().get_command()} tar {options} -czvf '{self.target_path}' -C '{source_dir}' '{source_file}'"

    def get_extract_command(self) -> str:

        return f"{super().get_command()} tar -xzf '{self.source_path}' -C '{self.target_path}'"

    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        return stdout
