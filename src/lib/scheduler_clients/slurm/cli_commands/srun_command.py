# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from lib.exceptions import SlurmError
from lib.ssh_clients.ssh_client import BaseCommand


class SrunCommand(BaseCommand):

    def __init__(
        self,
        job_id: str = None,
        overlap: bool = True,
        command: str = "",
    ) -> None:
        super().__init__()
        self.job_id = job_id
        self.overlap = overlap
        self.command = command

    def get_command(self) -> str:
        cmd = ["srun"]
        if self.job_id:
            cmd += [f"--jobid='{self.job_id}'"]
        if self.overlap:
            cmd += ["--overlap"]
        cmd += [self.command]

        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )
