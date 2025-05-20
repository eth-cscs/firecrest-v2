# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.exceptions import PbsError
from lib.scheduler_clients.slurm.cli_commands.scontrol_base import ScontrolBase
from typing import List
import json


class PbsPartitionsCommand(ScontrolBase):

    def __init__(self, username: str = None, part_ids: List[str] = None) -> None:
        super().__init__()
        self.username = username
        self.part_ids = part_ids if part_ids else []

    def get_command(self) -> str:
        cmd = ["qstat", "-F", "json", "-f", "-Q"] + self.part_ids
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS command response. exit_status:{exit_status} std_err:{stderr}"
            )

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise PbsError(
                f"Failed to parse JSON from qstat output: {e}\nOutput was:\n{stdout!r}"
            )

        queues_data = payload.get("Queue")
        if queues_data is None:
            return []

        result = []
        for name, attrs in queues_data.items():
            info = {}
            info["name"] = name
            info["type"] = attrs.get("queue_type")
            state = "enabled" if attrs.get("enabled") else "disabled"
            state += "&"
            state += "started" if attrs.get("started") else "stopped"
            info["state"] = state

            result.append(info)

        return result
