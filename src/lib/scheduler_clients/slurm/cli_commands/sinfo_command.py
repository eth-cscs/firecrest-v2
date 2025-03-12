# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

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
        cmd = ["sinfo -N"]
        cmd += ["--noheader"]
        cmd += ["--format='%z|%c|%O|%e|%f|%N|%o|%n|%T|%R|%w|%v|%m|%C'"]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        nodes = {}
        for node_str in stdout.split("\n"):
            node_info = node_str.split("|")
            if len(node_info) != 14:
                continue

            node_name = node_info[5]
            if node_name in nodes:
                nodes[node_name]["partitions"] += node_info[9].split(",")
            else:
                nodes[node_name] = {
                    "sockets": _int_or_none(node_info[0].split(":")[0]),
                    "cores": _int_or_none(node_info[0].split(":")[0]),
                    "threads": _int_or_none(node_info[0].split(":")[0]),
                    "cpus": _int_or_none(node_info[1]),
                    "cpu_load": _float_or_none(node_info[2]),
                    "free_memory": _int_or_none(node_info[3]),
                    "features": node_info[4],
                    "name": node_info[5],
                    "address": node_info[6],
                    "hostname": node_info[7],
                    "state": node_info[8],
                    "partitions": node_info[9].split(","),
                    "weight": _int_or_none(node_info[10]),
                    "slurmd_version": node_info[11],
                    "alloc_memory": _int_or_none(node_info[12]),
                    "alloc_cpus": _int_or_none(node_info[13].split("/")[0]),
                    "idle_cpus": _int_or_none(node_info[13].split("/")[1]),
                }

        if len(nodes) == 0:
            return None
        return nodes.values()
