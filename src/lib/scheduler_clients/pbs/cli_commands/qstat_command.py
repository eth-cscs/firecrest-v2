# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.exceptions import PbsError
import json


from lib.scheduler_clients.pbs.cli_commands.qstat_base import QstatBaseCommand


class QstatCommand(QstatBaseCommand):

    def get_command(self):
        cmd = super().get_command() + " -x"
        # For some reason qstat ignores the json format when using the -u
        # option, so we have to filter the output ourselves during the
        # parsing.
        # if not self.allusers:
        #     cmd += f" -u {self.username}"
        return cmd

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS qstat response. exit_status:{exit_status} std_err:{stderr}"
            )

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise PbsError(
                f"Failed to parse JSON from qstat output: {e!s}\nOutput was:\n{stdout!r}"
            ) from e

        res = payload.get("Jobs", {})
        jobs = []
        for job_id, job_data in res.items():
            job_owner = job_data.get("Job_Owner", "").split("@")[0]
            if not self.allusers and job_owner != self.username:
                continue

            job_id_parsed = int(job_id.split(".")[0])
            job_info = {
                "job_id": job_id_parsed,
                **job_data,
            }
            job_info["user"] = job_owner
            jobs.append(job_info)

        return jobs
