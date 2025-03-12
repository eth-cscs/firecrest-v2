# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
import re
from lib.exceptions import SlurmError
from lib.ssh_clients.ssh_client import BaseCommand


class ScancelCommand(BaseCommand):

    def __init__(self, username: str, job_ids: str) -> None:
        super().__init__()
        self.username = username
        self.job_ids = job_ids

    def get_command(self) -> str:
        cmd = ["scancel"]
        # TODO: investigate why this option is causing issues with the scancel command
        # cmd += [f"--user={username}"]
        cmd += ["--verbose"]
        cmd += [self.job_ids]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )
        has_error = re.search(".+error:.*", stderr, re.IGNORECASE)
        if has_error:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )
        return True
