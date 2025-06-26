# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
from lib.exceptions import PbsError
from lib.scheduler_clients.models import JobDescriptionModel
from lib.ssh_clients.ssh_client import BaseCommand


class QsubCommand(BaseCommand):

    def __init__(self, job_description: JobDescriptionModel) -> None:
        super().__init__()
        self.job_description = job_description

    def get_command(self) -> str:
        cmd = ["qsub"]

        if self.job_description.environment:
            env_list = [
                f"{key}={value}"
                for key, value in self.job_description.environment.items()
            ]
            cmd.append(f"-v {','.join(env_list)}")
        else:
            cmd.append("-V")

        if self.job_description.name:
            cmd.append(f"-N '{self.job_description.name}'")
        if self.job_description.account:
            cmd.append(f"-P '{self.job_description.account}'")
        if self.job_description.standard_error:
            cmd.append(f"-e '{self.job_description.standard_error}'")
        if self.job_description.standard_output:
            cmd.append(f"-o '{self.job_description.standard_output}'")

        # The last argument is the script to run
        if self.job_description.script_path:
            cmd.append(f" -- {self.job_description.script_path}")

        submit_cmd = " ".join(cmd)
        if self.job_description.current_working_directory:
            submit_cmd = (
                f"cd {self.job_description.current_working_directory} && "
                f"{submit_cmd}"
            )

        return submit_cmd

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS command response. exit_status:{exit_status} std_err:{stderr} stdout:{stdout}"
            )
        match = re.match(r"^(\d+)", stdout.strip())
        if match:
            return match.group(1)
        return None
