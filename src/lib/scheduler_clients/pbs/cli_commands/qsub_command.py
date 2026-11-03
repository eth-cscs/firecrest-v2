# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
import shlex
from lib.exceptions import PbsError, PbsRequestError
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
            cmd.append(f"-v {shlex.quote(','.join(env_list))}")
        else:
            cmd.append("-V")

        if self.job_description.name:
            cmd.append(f"-N {shlex.quote(self.job_description.name)}")
        if self.job_description.reservation:
            cmd.append(f"-q {shlex.quote(self.job_description.reservation)}")
        elif self.job_description.partition:
            cmd.append(f"-q {shlex.quote(self.job_description.partition)}")
        if self.job_description.account:
            cmd.append(f"-P {shlex.quote(self.job_description.account)}")
        if self.job_description.standard_error:
            cmd.append(f"-e {shlex.quote(self.job_description.standard_error)}")
        if self.job_description.standard_output:
            cmd.append(f"-o {shlex.quote(self.job_description.standard_output)}")

        # A command line select replaces the script's whole select, so it is
        # only sent when nodes is given. Per-node resources can't be sent
        # without it: PBS rejects them next to a script's select.
        tasks = self.job_description.tasks_per_node
        cpus = self.job_description.cpus_per_task
        memory = self.job_description.memory_per_node
        if not self.job_description.nodes and (tasks or cpus or memory):
            raise PbsRequestError(
                "tasksPerNode, cpusPerTask and memoryPerNode require nodes on PBS"
            )
        if self.job_description.nodes:
            # One chunk per node; place=scatter keeps chunks on separate
            # nodes, like Slurm's --nodes
            select = [str(self.job_description.nodes)]
            if tasks and cpus:
                select.append(f"ncpus={tasks * cpus}")
            if tasks:
                select.append(f"mpiprocs={tasks}")
                if cpus:
                    select.append(f"ompthreads={cpus}")
            if memory:
                # PBS "mb" is MiB, matching memory_per_node
                select.append(f"mem={memory}mb")
            cmd.append(f"-l select={':'.join(select)}")
            cmd.append("-l place=scatter")
        if self.job_description.time_limit:
            hours, minutes = divmod(self.job_description.time_limit, 60)
            cmd.append(f"-l walltime={hours:02d}:{minutes:02d}:00")

        # The last argument is the script to run
        if self.job_description.script_path:
            cmd.append(f"-- {shlex.quote(self.job_description.script_path)}")

        submit_cmd = " ".join(cmd)
        if self.job_description.current_working_directory:
            submit_cmd = (
                f"cd {shlex.quote(self.job_description.current_working_directory)} && "
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
