# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
from lib.exceptions import PbsError
from lib.scheduler_clients.pbs.models import PbsJobDescription
from lib.ssh_clients.ssh_client import BaseCommand


class QsubCommand(BaseCommand):

    def __init__(self, job_description: PbsJobDescription) -> None:
        super().__init__()
        self.job_description = job_description

    def get_command(self) -> str:
        cmd = ["/opt/pbs/bin/qsub"]

        # Export environment variables (-v) or all (-V)
        if self.job_description.environment:
            env_list = [
                f"{key}={value}"
                for key, value in self.job_description.environment.items()
            ]
            cmd.append(f"-v {','.join(env_list)}")
        else:
            cmd.append("-V")

        # FIXME: This is not working for the openpbs containers
        # if self.job_description.current_working_directory:
        #     cmd.append(f"-d '{self.job_description.current_working_directory}'")
        if self.job_description.name:
            cmd.append(f"-N '{self.job_description.name}'")
        if self.job_description.standard_error:
            cmd.append(f"-e '{self.job_description.standard_error}'")
        if self.job_description.standard_output:
            cmd.append(f"-o '{self.job_description.standard_output}'")
        # if self.job_description.standard_input:
        #     cmd.append(f"-i '{self.job_description.standard_input}'")

        # if self.job_description.constraints:
        #     cmd.append(f"-l {self.job_description.constraints}")

        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS command response. exit_status:{exit_status} std_err:{stderr}"
            )
        match = re.match(r"^(\d+)", stdout.strip())
        if match:
            return match.group(1)
        return None
