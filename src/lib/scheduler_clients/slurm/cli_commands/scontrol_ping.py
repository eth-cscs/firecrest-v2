# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.scontrol_base import ScontrolBase
import re


class ScontrolPingCommand(ScontrolBase):

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += ["ping"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        pings = []

        for ping_str in stdout.split("\n"):
            if len(ping_str) == 0:
                continue
            ping = {}
            attr_match = re.search(r"Slurmctld\((\S+)\) at (\S+) is (\S+)", ping_str)
            if attr_match:
                ping["primary"] = attr_match.group(1).startswith("primary")
                ping["hostname"] = attr_match.group(2)
                ping["responding"] = attr_match.group(3).startswith("UP")
            else:
                raise ValueError("Could not parse ping output")

            pings.append(ping)

        if len(pings) == 0:
            return None
        return pings
