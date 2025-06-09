# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
from lib.exceptions import PbsError
from lib.scheduler_clients.pbs.cli_commands.qstat_base import QstatBaseCommand


class PbsPingCommand(QstatBaseCommand):

    def get_command(self):
        cmd = super().get_command() + " -B"
        return cmd

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS command response. exit_status:{exit_status} std_err:{stderr}"
            )

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise PbsError(
                f"Failed to parse JSON from qstat output: {e!s}\nOutput was:\n{stdout!r}"
            ) from e

        servers = []

        servers_data = payload.get("Server")
        for server_name, server_data in servers_data.items():
            server_info = {
                "hostname": server_name,
            }
            state = server_data.get("server_state")
            if state == "Active":
                server_info["pinged"] = "UP"
            else:
                server_info["pinged"] = "DOWN"

            servers.append(server_info)

        return servers
