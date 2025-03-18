# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from firecrest.filesystem.ops.commands.ls_base_command import LsBaseCommand


class LsCommand(LsBaseCommand):

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
        return super().get_command()
