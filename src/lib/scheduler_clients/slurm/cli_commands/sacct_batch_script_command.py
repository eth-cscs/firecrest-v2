# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
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
        parts = stdout.split(
            "--------------------------------------------------------------------------------\n"
        )
        for header, script in zip(parts[0::2], parts[1::2], strict=True):
            jobs.append(
                {
                    "jobId": int(header[17:]),
                    "script": script,
                }
            )
        if len(jobs) == 0:
            return None
        return jobs
