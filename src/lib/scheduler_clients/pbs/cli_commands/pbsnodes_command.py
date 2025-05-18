# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
from lib.exceptions import PbsError
from lib.ssh_clients.ssh_client import BaseCommand


class PbsnodesCommand(BaseCommand):
    """
    Command to list PBS nodes. Uses `pbsnodes -a` to retrieve all node attributes,
    and parses the output into a list of node dictionaries.
    """

    def __init__(self, show_all: bool = True) -> None:
        super().__init__()
        self.show_all = show_all

    def get_command(self) -> str:
        cmd = ["/opt/pbs/bin/pbsnodes"]
        if self.show_all:
            cmd.append("-a")
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise PbsError(
                f"Unexpected PBS pbsnodes response. exit_status:{exit_status} std_err:{stderr}"
            )

        nodes = []
        current = {}

        for line in stdout.splitlines():
            # Blank line separates node entries
            if not line.strip():
                if current:
                    nodes.append(current)
                    current = {}
                continue

            # Node name line (no indent)
            if not line.startswith(" ") and not line.startswith("\t"):
                # Start new node
                if current:
                    nodes.append(current)
                current = {"name": line.strip()}
                continue

            # Attribute line: key = value
            parts = line.strip().split("=", 1)
            if len(parts) != 2 or not current:
                continue
            key, val = parts[0].strip(), parts[1].strip()

            if key == "state":
                current["state"] = val
            elif key == "np":
                try:
                    current["np"] = int(val)
                except ValueError:
                    current["np"] = val
            elif key == "properties":
                current["properties"] = val
            elif key in ("gpus", "gpuInfo"):
                current["gin"] = val
            elif key in ("phys_memory", "resources_available.mem"):
                # Extract leading integer
                m = re.match(r"(\d+)", val)
                current["memory"] = int(m.group(1)) if m else val
            elif key in ("swap", "swapMemory"):  # if swap info available
                m = re.match(r"(\d+)", val)
                current["swap"] = int(m.group(1)) if m else val

        # Append last node
        if current:
            nodes.append(current)

        return nodes if nodes else None
