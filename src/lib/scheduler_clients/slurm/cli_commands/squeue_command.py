# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from typing import List
from lib.scheduler_clients.slurm.cli_commands.sacct_job_info_command import SacctCommand
from lib.exceptions import SlurmError


class SqueueCommand(SacctCommand):

    def __init__(
        self,
        username: str = None,
        job_ids: List[str] = None,
        allusers: bool = False,
        account: str = None,
    ) -> None:
        super().__init__()
        self.username = username
        self.allusers = allusers
        self.job_ids = job_ids
        self.account = account

    def get_command(self) -> str:
        cmd = ["SLURM_TIME_FORMAT='%s' squeue"]
        if not self.allusers:
            cmd += ["--user=" + self.username]  # show only user jobs
        if self.account:
            cmd += [f"--account='{self.account}'"]
        if self.job_ids:
            str_job_ids = ",".join(self.job_ids)
            cmd += [f"--job='{str_job_ids}'"]
        cmd += [
            "--noheader",
            # "--Format='JobID,AllocNodes,,,GroupId,Account,Name,NodeList,Partition,Priority,State,Reason,TimeUsed,SubmitTime,StartTime,EndTime,TimeLimit,,UserName,WorkDir'"
            # Note ElapsedRaw, TimelimitRaw are not available in squeue
            # Note priority is provided in a different format in squeue and sacct
            "--format='%i|%D|||%g|%a|%j|%N|%P||%T|%r||%V|%S|%E|||%u|%Z'",
        ]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        return super().parse_output(stdout, stderr, exit_status)
