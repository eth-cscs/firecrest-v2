# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandWithTimeoutErrorHandling,
)
from lib.ssh_clients.ssh_client import BaseCommand

UTILITIES_TIMEOUT = 5
UTILITIES_MAX_FILE = 5 * 1024 * 1024  # 5MB


class IdCommand(BaseCommand, BaseCommandWithTimeoutErrorHandling):

    def __init__(
        self,
    ) -> None:
        super().__init__()

    def get_command(
        self,
    ) -> str:
        return f"timeout {UTILITIES_TIMEOUT} id"

    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        uid_i = stdout.find("=", 0)
        uname_i = stdout.find("(", stdout.find("uid=", 0))
        uname_j = stdout.find(")", stdout.find("uid=", 0))
        uname = stdout[uname_i + 1 : uname_j]
        uid = stdout[uid_i + 1 : uname_i]
        user_json = {"name": uname, "id": uid}

        gid_i = stdout.find("=", uname_j)
        gname_i = stdout.find("(", stdout.find("gid=", 0))
        gname_j = stdout.find(")", stdout.find("gid=", 0))
        gname = stdout[gname_i + 1 : gname_j]
        gid = stdout[gid_i + 1 : gname_i]
        group_json = {"name": gname, "id": gid}

        groups = []

        group_list = stdout[stdout.find("=", gname_j) + 1 :].split(",")

        for group in group_list:
            gname_i = group.find("(", 0)
            gname_j = group.find(")", 0)
            gname = group[gname_i + 1 : gname_j]
            gid = group[:gname_i]

            groups.append({"name": gname, "id": gid})

        return {"user": user_json, "group": group_json, "groups": groups}
