# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from abc import abstractmethod
from typing import List
from lib.scheduler_clients.models import JobsTimeWindow
from lib.ssh_clients.ssh_client import BaseCommand

# sacct relative --starttime value for each supported historical time window
_SACCT_STARTTIME_BY_TIME_WINDOW = {
    JobsTimeWindow.LAST_HOUR: "now-1hours",
    JobsTimeWindow.LAST_8_HOURS: "now-8hours",
    JobsTimeWindow.LAST_24_HOURS: "now-24hours",
    JobsTimeWindow.LAST_3_DAYS: "now-3days",
    JobsTimeWindow.LAST_7_DAYS: "now-7days",
}


class SacctCommandBase(BaseCommand):

    def __init__(
        self,
        username: str = None,
        job_ids: List[str] = None,
        allusers: bool = False,
        account: str = None,
        time_window: JobsTimeWindow = JobsTimeWindow.LAST_24_HOURS,
    ) -> None:
        super().__init__()
        self.username = username
        self.allusers = allusers
        self.job_ids = job_ids
        self.account = account
        self.time_window = time_window

    def get_command(self) -> str:
        cmd = ["SLURM_TIME_FORMAT='%s' sacct"]
        if self.allusers:
            cmd += ["--allusers"]
        if self.account:
            cmd += [f"--account='{self.account}'"]
        if self.job_ids:
            str_job_ids = ",".join(self.job_ids)
            cmd += [f"--jobs='{str_job_ids}'"]
        else:
            cmd += [f"--starttime={_SACCT_STARTTIME_BY_TIME_WINDOW[self.time_window]}"]
        cmd += ["--parsable2"]
        return " ".join(cmd)

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        pass
