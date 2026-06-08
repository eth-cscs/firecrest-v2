# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.exceptions import SlurmError
import re
from datetime import datetime

from lib.scheduler_clients.slurm.cli_commands.scontrol_base import ScontrolBase


def _null_to_none(string: str):
    if string == "(null)":
        return None
    return string


class ScontrolReservationCommand(ScontrolBase):

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += ["-a show -o reservations"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        if stdout.lower().startswith("no reservations"):
            return []

        attributes = [
            {
                "name": "ReservationName",
                "pattern": r"ReservationName=(\S+)",
                "type": "str",
            },
            {"name": "State", "pattern": r"State=(\S+)", "type": "str"},
            {"name": "Nodes", "pattern": r"Nodes=(\S+)", "type": "str"},
            {
                "name": "StartTime",
                "pattern": r"StartTime=((\d{1,2} \S+ \d{2}:\d{2})|(\d{2}:\d{2}:\d{2})|(\d{1,2} \S+ \d{4})|(\d{1,4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}))",
                "type": "datetime",
            },
            {
                "name": "EndTime",
                "pattern": r"EndTime=((\d{1,2} \S+ \d{2}:\d{2})|(\d{2}:\d{2}:\d{2})|(\d{1,2} \S+ \d{4})|(\d{1,4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}))",
                "type": "datetime",
            },
            {"name": "Features", "pattern": r"Features=(\S+)", "type": "str"},
        ]
        reservations = []

        for reservation_str in stdout.split("\n"):
            if len(reservation_str) == 0:
                continue
            reservation = {}
            for attribute in attributes:
                attr_match = re.search(rf"{attribute['pattern']}", reservation_str)
                if attr_match:
                    if attribute["type"] == "datetime":
                        date = None
                        try:
                            date = datetime.fromisoformat(attr_match.group(1))
                        except ValueError:
                            pass
                        try:
                            date = datetime.strptime(
                                datetime.today().strftime("%Y")
                                + " "
                                + attr_match.group(1),
                                "%Y %d %b %H:%M",
                            )
                        except ValueError:
                            pass
                        try:
                            date = datetime.strptime(
                                attr_match.group(1),
                                "%d %b %Y",
                            )
                        except ValueError:
                            pass
                        try:
                            date = datetime.strptime(
                                datetime.today().strftime("%m/%d/%y")
                                + " "
                                + attr_match.group(1),
                                "%m/%d/%y %H:%M:%S",
                            )
                        except ValueError:
                            pass
                        if date is None:
                            raise ValueError("Unable to parse reservation datatime")

                        reservation[attribute["name"]] = date.timestamp()
                    else:
                        reservation[attribute["name"]] = _null_to_none(
                            attr_match.group(1)
                        )
                else:
                    raise ValueError(
                        f"Could not parse attribute '{attribute['name']}' in "
                        f"'{reservation_str}'"
                    )

            reservations.append(reservation)

        return reservations
