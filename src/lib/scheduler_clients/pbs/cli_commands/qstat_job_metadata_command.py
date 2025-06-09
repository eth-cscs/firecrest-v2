# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
from lib.exceptions import PbsError

from lib.scheduler_clients.pbs.cli_commands.qstat_base import QstatBaseCommand
from lib.scheduler_clients.models import JobMetadataModel


class QstatJobMetadataCommand(QstatBaseCommand):

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
            jobs.append(JobMetadataModel(job_id=int(job_id.split(".")[0]), **job_data))

        return jobs
