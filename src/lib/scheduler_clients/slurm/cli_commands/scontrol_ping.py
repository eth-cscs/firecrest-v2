# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.scontrol_base import ScontrolBase


class ScontrolPingCommand(ScontrolBase):

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += ["ping"]
        cmd += ["--json"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        pings = []
        raw_pings = json.loads(stdout)["pings"]
        for raw_ping in raw_pings:
            pings.append(
                {
                    "mode": raw_ping["mode"],
                    "hostname": raw_ping["hostname"],
                    "pinged": raw_ping["pinged"],
                }
            )

        if len(pings) == 0:
            return None
        return pings
