# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
from lib.exceptions import SlurmError
from lib.ssh_clients.ssh_client import BaseCommand


def _float_or_none(floatstr: str):
    try:
        return float(floatstr)
    except Exception:
        return None


def _int_or_none(intstr: str):
    try:
        return int(intstr)
    except Exception:
        return None


class SinfoCommand(BaseCommand):

    def get_command(self) -> str:
        cmd = ["sinfo -a -N"]
        cmd += ["--noheader"]
        cmd += ["--format='%z|%c|%O|%e|%f|%N|%o|%n|%T|%R|%w|%v|%m|%C'"]
        cmd += ["--json"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        nodes = []
        raw_nodes = json.loads(stdout)["sinfo"]
        for raw_node in raw_nodes:
            nodes.append(
                {
                    "sockets": raw_node["sockets"]["minimum"],
                    "cores": raw_node["cores"]["minimum"],
                    "threads": raw_node["threads"]["minimum"],
                    "cpus": raw_node["cpus"]["total"],
                    "cpu_load": raw_node["cpus"]["load"]["minimum"],
                    "free_memory": raw_node["memory"]["free"]["minimum"]["number"],
                    "features": raw_node["features"]["active"],
                    "name": raw_node["nodes"]["nodes"][0],
                    "address": raw_node["nodes"]["addresses"][0],
                    "hostname": raw_node["nodes"]["hostnames"][0],
                    "state": raw_node["node"]["state"][0],
                    "partitions": raw_node["partition"]["name"].split(","),
                    "weight": raw_node["weight"]["minimum"],
                    # "slurmd_version": node_info[11],
                    "alloc_memory": raw_node["memory"]["allocated"],
                    "alloc_cpus": raw_node["cpus"]["allocated"],
                    "idle_cpus": raw_node["cpus"]["idle"],
                }
            )

        if len(nodes) == 0:
            return None
        return nodes
