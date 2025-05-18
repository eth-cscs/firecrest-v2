# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
from lib.exceptions import PbsError
from lib.ssh_clients.ssh_client import BaseCommand


class PbsPingCommand(BaseCommand):

    def get_command(self) -> str:
        # Request full server status, which includes 'Server:' header and attribute lines
        return "/opt/pbs/bin/qstat -Bf"

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS command response. exit_status:{exit_status} std_err:{stderr}"
            )

        pings = []
        current = {}

        for line in stdout.splitlines():
            # Header with server name
            host_match = re.match(r"Server:\s+(\S+)", line)
            if host_match:
                # start a new ping record
                if current:
                    pings.append(current)
                    current = {}
                current["hostname"] = host_match.group(1)
                continue

            # Server state attribute
            state_match = re.match(r"\s*server_state\s*=\s*(\S+)", line)
            if state_match and current is not None:
                if state_match.group(1) == "Active":
                    current["pinged"] = "UP"
                else:
                    current["pinged"] = "DOWN"
                continue

        # append last record
        if current:
            pings.append(current)

        return pings if pings else None
