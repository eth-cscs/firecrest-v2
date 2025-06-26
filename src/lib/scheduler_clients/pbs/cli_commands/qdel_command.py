# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.exceptions import PbsError
from lib.ssh_clients.ssh_client import BaseCommand


class QdelCommand(BaseCommand):

    def __init__(self, username: str, job_id: str) -> None:
        super().__init__()
        self.username = username
        self.job_id = job_id

    def get_command(self) -> str:
        cmd = ["qdel"]
        cmd += [self.job_id]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS qdel response. exit_status:{exit_status} std_err:{stderr}"
            )

        return True
