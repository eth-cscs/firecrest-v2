# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
import re
from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.models import SlurmJobDescription
from lib.ssh_clients.ssh_client import BaseCommand


class SbatchCommand(BaseCommand):

    def __init__(self, job_description: SlurmJobDescription) -> None:
        super().__init__()
        self.job_description = job_description

    def get_command(self) -> str:
        cmd = ["sbatch"]
        env = ",".join(f"{key}={value}"
                       for key, value
                       in self.job_description.environment.items())
        cmd += [f"--export='ALL,{env}'"]
        cmd += [f"--chdir='{self.job_description.current_working_directory}'"]
        if self.job_description.name:
            cmd.append(f"--job-name='{self.job_description.name}'")
        if self.job_description.standard_error:
            cmd += [f"--error='{self.job_description.standard_error}'"]
        if self.job_description.standard_output:
            cmd += [f"--output='{self.job_description.standard_output}'"]
        if self.job_description.standard_input:
            cmd += [f"--input='{self.job_description.standard_input}'"]
        if self.job_description.constraints:
            cmd.append(f"--constraint='{self.job_description.constraints}'")
        if self.job_description.script_path:
            cmd.append(f" -- {self.job_description.script_path}")
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )
        job_id_search = re.search("Submitted batch job ([0-9]+)", stdout, re.IGNORECASE)
        if job_id_search:
            return job_id_search.group(1)
        return None
