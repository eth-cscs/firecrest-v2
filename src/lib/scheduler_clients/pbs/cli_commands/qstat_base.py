# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import List, Optional
from lib.ssh_clients.ssh_client import BaseCommand


class QstatBaseCommand(BaseCommand):

    def __init__(
        self,
        username: str = None,
        ids: Optional[List[str]] = None,
        allusers: bool = True,
        account: str = None,
    ) -> None:
        super().__init__()
        self.username = username
        self.ids = ids if ids else []
        self.allusers = allusers
        self.account = account

    def get_command(self) -> str:
        cmd = ["qstat", "-F", "json", "-f"] + self.ids
        if self.account:
            cmd += ["-A", self.account]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        pass
