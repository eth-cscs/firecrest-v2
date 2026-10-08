# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.sacctmgr_base import SacctmgrBaseCommand


class SacctmgrAccountsCommand(SacctmgrBaseCommand):

    username: str

    def __init__(self, username: str = None) -> None:
        super().__init__()
        self.username = username

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += ["show assoc"]
        cmd += [f"user='{self.username}'"]
        # -P: parsable output, otherwise names longer than the column
        # width (10) are truncated, e.g. "project-a-1" -> "project-a+"
        cmd += ["format=account -n -P"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        accounts = []
        for line in stdout.split("\n"):
            if line.strip() == "":
                continue
            account = line.strip()
            # One association row is listed per partition/cluster
            if account not in accounts:
                accounts.append(account)

        if len(accounts) == 0:
            return None
        return accounts
