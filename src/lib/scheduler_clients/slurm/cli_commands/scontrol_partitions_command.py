# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.scontrol_base import ScontrolBase
import re


class ScontrolPartitionCommand(ScontrolBase):

    def __init__(self, all: bool = False) -> None:
        super().__init__()
        self.all = all

    def get_command(self) -> str:
        cmd = [super().get_command()]
        if self.all:
            cmd += ["-a"]
        cmd += ["show -o partitions"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        attributes = [
            "PartitionName",
            "State",
            "TotalCPUs",
            "TotalNodes",
        ]
        partitions = []

        for partition_str in stdout.split("\n"):
            if len(partition_str) == 0:
                continue
            partition = {}
            for attr_name in attributes:
                attr_match = re.search(rf"{attr_name}=(\S+)", partition_str)
                if attr_match:
                    partition[attr_name] = attr_match.group(1)
                else:
                    raise ValueError(
                        f"Could not parse attribute '{attr_name}' in "
                        f"'{partition_str}'"
                    )

            partitions.append(partition)

        if len(partitions) == 0:
            return None
        return partitions
