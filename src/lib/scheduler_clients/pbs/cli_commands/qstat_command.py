# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
from lib.exceptions import PbsError
from typing import List


from lib.ssh_clients.ssh_client import BaseCommand


class QstatCommand(BaseCommand):

    def __init__(self, username: str = None, job_ids: List[str] = None) -> None:
        super().__init__()
        self.username = username
        self.job_ids = job_ids

    def get_command(self) -> str:
        cmd = ["/opt/pbs/bin/qstat", "-f"] + self.job_ids
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
            status = {
                # FIXME: qstat does not return the exit code
                # Make it optional or run additional commands
                # to get the exit code
                "exitCode": 0,
            }
            times = {}

            for line in block.splitlines():
                line = line.strip()
                if line.startswith("Job Id:"):
                    full_job_id = line.split(":", 1)[1].strip()
                    info["job_id"] = full_job_id.split(".")[0]
                elif line.startswith("Job_Name"):
                    info["name"] = line.split("=", 1)[1].strip()
                elif line.startswith("job_state"):
                    status["state"] = line.split("=", 1)[1].strip()
                elif line.startswith("exit_status"):
                    try:
                        status["exitCode"] = int(line.split("=", 1)[1].strip())
                    except ValueError:
                        status["exitCode"] = None

                elif line.startswith("resources_used.walltime"):
                    times["elapsed"] = line.split("=", 1)[1].strip()
                elif line.startswith("stime"):
                    times["start"] = line.split("=", 1)[1].strip()
                elif line.startswith("Resource_List.walltime"):
                    times["limit"] = line.split("=", 1)[1].strip()
                elif line.startswith("Job_Owner"):
                    owner = line.split("=", 1)[1].strip()
                    if "@" in owner:
                        user, cluster = owner.split("@", 1)
                        info["user"] = user
                        info["cluster"] = cluster
                    else:
                        info["user"] = owner

                elif line.startswith("project"):
                    info["account"] = line.split("=", 1)[1].strip()

                elif line.startswith("Resource_List.nodect"):
                    try:
                        info["allocation_nodes"] = int(line.split("=", 1)[1].strip())
                    except ValueError:
                        info["allocation_nodes"] = None

                elif line.startswith("queue"):
                    info["partition"] = line.split("=", 1)[1].strip()

                elif line.startswith("Resource_List.nodes"):
                    info["nodes"] = line.split("=", 1)[1].strip()

                elif line.startswith("Priority"):
                    try:
                        info["priority"] = int(line.split("=", 1)[1].strip())
                    except ValueError:
                        info["priority"] = None

                elif line.startswith("jobdir"):
                    info["working_directory"] = line.split("=", 1)[1].strip()

            info["status"] = status
            info["time"] = times

            jobs.append(info)

        return jobs
