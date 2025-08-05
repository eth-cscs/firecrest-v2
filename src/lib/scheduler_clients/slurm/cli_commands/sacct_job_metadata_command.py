# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
import json
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
        raw_jobs = json.loads(stdout)["jobs"]
        for raw_job in raw_jobs:
            jobs.append(
                {
                    "jobId": raw_job["job_id"],
                    "jobName": raw_job["name"],
                    "standardInput": raw_job["stdin"],
                    "standardOutput": raw_job["stdout"],
                    "standardError": raw_job["stderr"],
                }
            )
        if len(jobs) == 0:
            return None
        return jobs
