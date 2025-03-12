# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandErrorHandling,
)
from lib.ssh_clients.ssh_client import BaseCommand

ID = 0
UTILITIES_TIMEOUT = 5


class StatCommand(BaseCommand, BaseCommandErrorHandling):

    def __init__(self, target_path: str = None, dereference: bool = False) -> None:
        super().__init__()
        self.target_path = target_path
        self.dereference = dereference

    def get_command(
        self,
    ) -> str:
        deref = ""
        if self.dereference:
            deref = "--dereference"
        return f"timeout {UTILITIES_TIMEOUT} stat {deref} -c '%f %i %d %h %u %g %s %X %Y %Z' -- '{self.target_path}'"

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        # follows: https://docs.python.org/3/library/os.html#os.stat_result
        # > stat --dereference -c '%f %i %d %h %u %g %s %X %Y %Z' -- source.txt
        # 81a4 64317775 50 1 26191 1000 8 1689669477 1685517840 1685517840
        # > stat source.txt
        #   File: source.txt
        #   Size: 8         	Blocks: 1          IO Block: 262144 regular file
        # Device: 32h/50d	Inode: 64317775    Links: 1
        # Access: (0644/-rw-r--r--)  Uid: (26191/fpagname)   Gid: ( 1000/ csstaff)
        # Access: 2023-07-18 10:37:57.526467355 +0200
        # Modify: 2023-05-31 09:24:00.804840000 +0200
        # Change: 2023-05-31 09:24:00.804742840 +0200
        #  Birth: -
        output = dict(
            zip(
                [
                    "mode",
                    "ino",
                    "dev",
                    "nlink",
                    "uid",
                    "gid",
                    "size",
                    "atime",
                    "mtime",
                    "ctime",
                ],
                stdout.split(),
            )
        )
        output["mode"] = int(output["mode"], base=16)
        output = {key: int(value) for key, value in output.items()}
        return output
