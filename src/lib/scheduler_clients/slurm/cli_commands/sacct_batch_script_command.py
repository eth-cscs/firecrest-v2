# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
import re
from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.sacct_base import SacctCommandBase


class SacctBatchScriptCommand(SacctCommandBase):

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += ["--batch-script"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        jobs = []
        pattern = r"^Batch Script for\s+(\d+)\n-+\n"
        blocks = re.split(pattern, stdout, flags=re.MULTILINE)

        for i in range(1, len(blocks), 2):
            jobs.append(
                {
                    "jobId": blocks[i].strip(),
                    "script": blocks[i + 1].strip(),
                }
            )
        if len(jobs) == 0:
            return None
        return jobs
