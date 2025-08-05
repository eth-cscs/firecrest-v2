# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.scontrol_base import ScontrolBase


class ScontrolPartitionCommand(ScontrolBase):

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += ["-a show -o partitions"]
        cmd += ["--json"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        partitions = []
        raw_partitions = json.loads(stdout)["partitions"]
        for raw_partition in raw_partitions:
            partitions.append(
                {
                    "PartitionName": raw_partition["name"],
                    "State": raw_partition["partition"]["state"][0],
                    "TotalCPUs": raw_partition["cpus"]["total"],
                    "TotalNodes": raw_partition["nodes"]["total"],
                }
            )

        if len(partitions) == 0:
            return None
        return partitions
