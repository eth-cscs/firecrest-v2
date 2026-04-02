# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.sacctmgr_base import SacctmgrBaseCommand


class SacctmgrDefaultAccountCommand(SacctmgrBaseCommand):

    username: str

    def __init__(self, username: str = None) -> None:
        super().__init__()
        self.username = username

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += ["show"]
        cmd += [f"user {self.username}"]
        cmd += ["format=defaultaccount -n"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        for line in stdout.split("\n"):
            if line.strip() == "":
                continue
            return line.strip()

        return None
