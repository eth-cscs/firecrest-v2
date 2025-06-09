# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.exceptions import PbsError
import json


from lib.scheduler_clients.pbs.cli_commands.qstat_base import QstatBaseCommand
from lib.scheduler_clients.models import JobModel


class QstatCommand(QstatBaseCommand):

    def get_command(self):
        cmd = super().get_command() + " -x"
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
            job_id_parsed = int(job_id.split(".")[0])
            nodes = job_data.get("Resource_List", {}).get("nodes", "")

            status = {}
            status["state"] = job_data.get("job_state", "")
            status["exitCode"] = int(job_data.get("Exit_status", 0))

            times = {}
            times["elapsed"] = job_data.get("resources_used", {}).get("walltime", None)
            times["start"] = job_data.get("stime", None)
            times["limit"] = job_data.get("Resource_List", {}).get("walltime", None)

            jobs.append(
                JobModel(
                    job_id=job_id_parsed,
                    nodes=nodes,
                    allocation_nodes=job_data.get("Resource_List", {}).get(
                        "nodect", None
                    ),
                    working_directory=job_data.get("Variable_List", {}).get(
                        "PBS_O_WORKDIR", ""
                    ),
                    status=status,
                    time=times,
                    **job_data,
                )
            )

        return jobs
