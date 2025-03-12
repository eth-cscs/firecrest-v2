# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from abc import abstractmethod
from typing import List
from lib.ssh_clients.ssh_client import BaseCommand


class SacctCommandBase(BaseCommand):

    def __init__(self, username: str = None, job_ids: List[str] = None) -> None:
        super().__init__()
        self.username = username
        self.job_ids = job_ids

    def get_command(self) -> str:
        cmd = ["sacct"]
        cmd += [f"--user={self.username}"]
        if self.job_ids:
            str_job_ids = ",".join(self.job_ids)
            cmd += [f"--jobs='{str_job_ids}'"]
        cmd += ["--noheader"]
        cmd += ["--parsable2"]

        return " ".join(cmd)

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        pass
