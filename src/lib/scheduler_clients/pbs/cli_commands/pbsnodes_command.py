# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
from lib.exceptions import PbsError
from lib.ssh_clients.ssh_client import BaseCommand
from lib.scheduler_clients.models import NodeModel


class PbsnodesCommand(BaseCommand):
    """
    Command to list PBS nodes. Uses `pbsnodes -a` to retrieve all node attributes,
    and parses the output into a list of node dictionaries.
    """

    def __init__(self) -> None:
        super().__init__()

    def get_command(self) -> str:
        cmd = ["pbsnodes", "-a", "-F", "json"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS pbsnodes response. exit_status:{exit_status} std_err:{stderr}"
            )

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise PbsError(
                f"Failed to parse JSON from pbsnodes output: {e}\nOutput was:\n{stdout!r}"
            ) from e

        nodes = []

        nodes_data = payload.get("nodes")
        for node_name, node_data in nodes_data.items():
            nodes.append(
                NodeModel(
                    name=node_name,
                    **node_data,
                )
            )

        return nodes
