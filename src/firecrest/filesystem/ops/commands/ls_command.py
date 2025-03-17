# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandWithTimeoutErrorHandling,
)
from firecrest.filesystem.ops.commands.ls_base_command import LsBaseCommand


UTILITIES_TIMEOUT = 5


class LsCommand(LsBaseCommand, BaseCommandWithTimeoutErrorHandling):

    def __init__(
        self,
        target_path: str = None,
        show_hidden: bool = False,
        numeric_uid: bool = False,
        recursive: bool = False,
        dereference: bool = False,
        no_recursion: bool = False,
    ) -> None:
        super().__init__(
            target_path, show_hidden, numeric_uid, recursive, dereference, no_recursion
        )

    def get_command(self) -> str:
        ls_cmd = super().get_command()
        return f"timeout {UTILITIES_TIMEOUT} " f"{ls_cmd}"
