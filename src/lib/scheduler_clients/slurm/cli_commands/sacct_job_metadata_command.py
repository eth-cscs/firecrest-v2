# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.sacct_base import SacctCommandBase


class SacctJobMetadataCommand(SacctCommandBase):

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += ["--format='JobID,JobName,StdIn,StdOut,StdErr'"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        jobs = []
        for job_str in stdout.split("\n"):
            job_info = job_str.split("|")
            if len(job_info) != 5:
                continue
            jobs.append(
                {
                    "jobId": job_info[0],
                    "jobName": job_info[1],
                    "standardInput": job_info[2],
                    "standardOutput": job_info[3],
                    "standardError": job_info[4],
                }
            )
        if len(jobs) == 0:
            return None
        return jobs
