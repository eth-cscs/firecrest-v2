# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.scontrol_base import ScontrolBase


class ScontrolJobCommand(ScontrolBase):

    def __init__(self, job_id: str = None) -> None:
        super().__init__()
        self.job_id = job_id

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += [f"show -o  job {self.job_id}"]
        cmd += ["--json"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            if stderr.find("Invalid job id specified") >= 0:
                return None

            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        jobs = []

        raw_jobs = json.loads(stdout)["jobs"]
        for raw_job in raw_jobs:
            jobs.append(
                {
                    "jobId": str(raw_job["job_id"]),
                    "name": raw_job["name"],
                    "standardInput": raw_job["standard_input"],
                    "standardOutput": raw_job["standard_output"],
                    "standardError": raw_job["standard_error"],
                }
            )

        if len(jobs) == 0:
            return None
        return jobs
