# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
from lib.exceptions import PbsError
from typing import List, Optional


from lib.ssh_clients.ssh_client import BaseCommand


class RstatReservationsCommand(BaseCommand):

    def __init__(
        self, username: str = None, res_ids: Optional[List[str]] = None
    ) -> None:
        super().__init__()
        self.username = username
        self.res_ids = res_ids

    def get_command(self) -> str:
        ids = self.res_ids if self.res_ids else []
        cmd = ["pbs_rstat", "-Sf"] + ids
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS qstat response. exit_status:{exit_status} std_err:{stderr}"
            )

        blocks = re.split(r"\n(?=Resv ID:)", stdout.strip())
        jobs = []

        # Clean up empty blocks
        blocks = [b for b in blocks if b]
        for block in blocks:
            info = {}

            for line in block.splitlines():
                line = line.strip()
                if line.startswith("Reserve_Name"):
                    info["name"] = line.split("=", 1)[1].strip()
                elif line.startswith("reserve_start"):
                    info["start_time"] = line.split("=", 1)[1].strip()
                elif line.startswith("reserve_end"):
                    info["end_time"] = line.split("=", 1)[1].strip()
                elif line.startswith("resv_nodes"):
                    info["node_list"] = line.split("=", 1)[1].strip()

            jobs.append(info)

        return jobs
