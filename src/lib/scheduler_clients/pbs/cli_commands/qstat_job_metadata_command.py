# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
from lib.exceptions import PbsError
from typing import List


from lib.ssh_clients.ssh_client import BaseCommand


class QstatJobMetadataCommand(BaseCommand):

    def __init__(self, username: str = None, job_ids: List[str] = None) -> None:
        super().__init__()
        self.username = username
        self.job_ids = job_ids

    def get_command(self) -> str:
        cmd = ["qstat", "-f"] + self.job_ids
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS qstat response. exit_status:{exit_status} std_err:{stderr}"
            )

        blocks = re.split(r"\n(?=Job Id:)", stdout.strip())
        jobs = []

        # Clean up empty blocks
        blocks = [b for b in blocks if b]
        for block in blocks:
            info = {}

            for line in block.splitlines():
                line = line.strip()
                if line.startswith("Job Id:"):
                    full_job_id = line.split(":", 1)[1].strip()
                    info["job_id"] = full_job_id.split(".")[0]
                elif line.startswith("Job_Name"):
                    info["name"] = line.split("=", 1)[1].strip()
                elif line.startswith("Output_Path"):
                    info["standardOutput"] = line.split("=", 1)[1].strip()
                elif line.startswith("Error_Path"):
                    info["standardError"] = line.split("=", 1)[1].strip()

            jobs.append(info)

        return jobs
