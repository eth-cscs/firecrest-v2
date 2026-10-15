# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
import shlex
from typing import List
from lib.scheduler_clients.slurm.cli_commands.sacct_base import SLURM_FIELD_DELIMITER
from lib.scheduler_clients.slurm.cli_commands.sacct_job_info_command import SacctCommand

# squeue fields, each followed by the given number of delimiters. Extra
# delimiters add empty columns so the output lines up with SacctCommand's
# format (ExitCode after Cluster, Suspended after EndTime).
SQUEUE_FIELDS = [
    ("JobID", 1),
    ("NumNodes", 1),
    ("Cluster", 2),
    ("GroupName", 1),
    ("Account", 1),
    ("Name", 1),
    ("NodeList", 1),
    ("Partition", 1),
    ("PriorityLong", 1),
    ("State", 1),
    ("Reason", 1),
    ("TimeUsed", 1),
    ("SubmitTime", 1),
    ("StartTime", 1),
    ("EndTime", 2),
    ("TimeLimit", 1),
    ("UserName", 1),
    ("WorkDir", 0),
]


class SqueueCommand(SacctCommand):

    def __init__(
        self,
        username: str = None,
        job_ids: List[str] = None,
        allusers: bool = False,
        account: str = None,
        name: str = None,
    ) -> None:
        super().__init__(
            username,
            job_ids,
            allusers,
            account,
            name
        )

    def get_command(self) -> str:
        cmd = ["SLURM_TIME_FORMAT='%s' squeue"]
        if not self.allusers:
            cmd += [f"--user={shlex.quote(self.username)}"]  # show only user jobs
        if self.account:
            cmd += [f"--account={shlex.quote(self.account)}"]
        if self.name:
            cmd += [f"--name={shlex.quote(self.name)}"]
        if self.job_ids:
            str_job_ids = ",".join(self.job_ids)
            cmd += [f"--jobs={shlex.quote(str_job_ids)}"]
        cmd += [
            "--noheader",
            "--Format='"
            + ",".join(
                f"{field}:{SLURM_FIELD_DELIMITER * separators}"
                for field, separators in SQUEUE_FIELDS
            )
            + "'",
        ]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        return super().parse_output(stdout, stderr, exit_status)
