# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
from lib.exceptions import SlurmError

from lib.scheduler_clients.slurm.cli_commands.scontrol_base import ScontrolBase


def _null_to_none(string: str):
    if string == "(null)":
        return None
    return string


class ScontrolReservationCommand(ScontrolBase):

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += ["-a show -o reservations"]
        cmd += ["--json"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        reservations = []
        raw_reservations = json.loads(stdout)["reservations"]
        for raw_reservation in raw_reservations:
            reservations.append(
                {
                    "ReservationName": raw_reservation["name"],
                    # "State": raw_reservation["state"],
                    "Nodes": raw_reservation["node_list"],
                    "StartTime": raw_reservation["start_time"]["number"],
                    "EndTime": raw_reservation["end_time"]["number"],
                    "Features": raw_reservation["features"],
                }
            )

        return reservations
