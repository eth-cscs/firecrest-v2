# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.scontrol_base import ScontrolBase


class ScontrolJobCommand(ScontrolBase):

    def __init__(self, job_id: str = None) -> None:
        super().__init__()
        self.job_id = job_id

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += [f"show -o  job {self.job_id}"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            if stderr.find("Invalid job id specified") >= 0:
                return None

            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        attributes = [
            "StdIn",
            "StdOut",
            "StdErr",
            "JobId",
        ]
        jobs = []

        for job_str in stdout.split("\n"):
            if len(job_str) == 0:
                continue
            job = {}
            for attr_name in attributes:
                attr_match = re.search(rf"{attr_name}=(\S+)", job_str)
                if attr_match:
                    job[attr_name] = attr_match.group(1)
                else:
                    job[attr_name] = None

            jobs.append(job)

        if len(jobs) == 0:
            return None
        return jobs
