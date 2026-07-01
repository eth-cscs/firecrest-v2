# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
import re
import shlex
from lib.exceptions import SlurmError

from lib.scheduler_clients.models import JobDescriptionModel
from lib.ssh_clients.ssh_client import BaseCommand


class SbatchCommand(BaseCommand):

    def __init__(self, job_description: JobDescriptionModel) -> None:
        super().__init__()
        self.job_description = job_description

    def get_command(self) -> str:
        cmd = ["sbatch"]
        env = ",".join(
            f"{key}={value}" for key, value in self.job_description.environment.items()
        )
        cmd += [f"--export={shlex.quote(f'ALL,{env}')}"]
        cmd += [f"--chdir={shlex.quote(self.job_description.current_working_directory)}"]
        if self.job_description.partition:
            cmd.append(f"--partition={shlex.quote(self.job_description.partition)}")
        if self.job_description.reservation:
            cmd.append(f"--reservation={shlex.quote(self.job_description.reservation)}")
        if self.job_description.account:
            cmd.append(f"--account={shlex.quote(self.job_description.account)}")
        if self.job_description.name:
            cmd.append(f"--job-name={shlex.quote(self.job_description.name)}")
        if self.job_description.standard_error:
            cmd += [f"--error={shlex.quote(self.job_description.standard_error)}"]
        if self.job_description.standard_output:
            cmd += [f"--output={shlex.quote(self.job_description.standard_output)}"]
        if self.job_description.standard_input:
            cmd += [f"--input={shlex.quote(self.job_description.standard_input)}"]
        if self.job_description.constraints:
            cmd.append(f"--constraint={shlex.quote(self.job_description.constraints)}")
        if self.job_description.script_path:
            cmd.append(f"-- {shlex.quote(self.job_description.script_path)}")
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
