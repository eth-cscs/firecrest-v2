# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from abc import abstractmethod
from typing import List
from lib.scheduler_clients.models import JobsTimeWindow
from lib.scheduler_clients.slurm.slurm_base_client import TIME_WINDOW_DURATIONS
from lib.ssh_clients.ssh_client import BaseCommand


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
            amount, unit = TIME_WINDOW_DURATIONS[self.time_window]
            # sacct's parse_time() accepts both singular and plural unit
            # names ("hour"/"hours"); use the grammatically correct one.
            if amount == 1:
                unit = unit[:-1]
            cmd += [f"--starttime=now-{amount}{unit}"]
        cmd += ["--parsable2"]
        return " ".join(cmd)

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        pass
