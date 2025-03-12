# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import re
import shlex
from fastapi import HTTPException, status

# commands
from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandErrorHandling,
)
from firecrest.filesystem.ops.models import File
from lib.ssh_clients.ssh_client import BaseCommand


UTILITIES_TIMEOUT = 5


class LsBaseCommand(BaseCommand, BaseCommandErrorHandling):

    def __init__(
        self,
        target_path: str = None,
        show_hidden: bool = False,
        numeric_uid: bool = False,
        recursion: bool = False,
        dereference: bool = False,
        no_recursion: bool = False,
    ) -> None:
        super().__init__()
        self.target_path = target_path
        self.no_recursion = no_recursion
        self.show_hidden = show_hidden
        self.numeric_uid = numeric_uid
        self.recursion = recursion
        self.dereference = dereference

        if self.no_recursion and self.recursion:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either the recursion or the no-recursion option can be set",
            )

    def get_command(self) -> str:
        options = "-l --quoting-style=c --time-style='+%Y-%m-%dT%H:%M:%S' "

        if self.show_hidden:
            # if set shows entries starting with . (not including . and/or .. dirs)
            options += "-A "
        if self.numeric_uid:
            # do not resolve UID and GID to names
            options += "--numeric-uid-gid "
        if self.no_recursion:
            options += "-d "
        if self.recursion:
            options += "-R "
        if self.dereference:
            options += "-L "

        return f"ls " f"{options}" f"-- '{self.target_path}'"

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        # Example of ls output
        # ".":
        # total 8
        # lrwxrwxrwx 1 username groupname 46 2023-07-25T14:18:00 "filename" -> "target link"
        # -rw-rw-r-- 1 root root           0 2023-07-24T11:45:35 "root_file.txt"
        # drwxrwxr-x 3 username groupname 4096 2023-07-24T11:45:35 "folder"
        # "./folder":
        # total 1
        # -rw-rw-r-- 1 username groupname 0 2023-07-24T11:45:35 "file_in_folder.txt"
        # ...

        def remove_prefix(text, prefix):
            return text[text.startswith(prefix) and len(prefix) :]

        if exit_status != 0:
            return super().error_handling(stderr, exit_status)

        file_list = []
        # Check if ls has recursive folders
        if re.match(r"\"(.+)\":\n", stdout):
            folders = re.split(r"\"(.+)\":\n", stdout)
            root_folder = ""
            for i in range(1, len(folders), 2):
                folder = folders[i].rstrip("/")
                if i == 1:
                    root_folder = folder + "/"
                folder_name = remove_prefix(folder + "/", root_folder)
                folder_content = folders[i + 1]
                file_list += self.ls_parse_folder(folder_content, folder_name)
        else:
            file_list += self.ls_parse_folder(stdout)

        if self.no_recursion:
            return file_list[0] if len(file_list) > 0 else None
        return file_list

    def ls_parse_folder(self, folder_content: str, path: str = ""):
        # Example of ls output
        # total 8
        # lrwxrwxrwx 1 username groupname 46 2023-07-25T14:18:00 'filename' -> 'target link'
        # -rw-rw-r-- 1 root root           0 2023-07-24T11:45:35 'root_file.txt'
        # ...
        file_pattern = (
            r"^(?P<type>\S)(?P<permissions>\S+)\s+\d+\s+(?P<user>\S+)\s+"
            r"(?P<group>\S+)\s+(?P<size>\d+)\s+(?P<last_modified>(\d|-|T|:)+)\s+(?P<filename>.+)$"
        )
        lines = folder_content.splitlines()
        file_list = []
        for entry in lines:
            matches = re.finditer(file_pattern, entry)
            for m in matches:
                tokens = shlex.split(m.group("filename"))
                if len(tokens) == 1:
                    name = tokens[0]
                    link_target = None
                elif len(tokens) == 3:
                    # We could add an assertion that m.group("type") == 'l' if
                    # we want to be sure that this is a link
                    name = tokens[0]
                    link_target = tokens[2]
                else:
                    continue
                file_list.append(
                    File(
                        name=path + name,
                        type=m.group("type"),
                        link_target=link_target,
                        user=m.group("user"),
                        group=m.group("group"),
                        permissions=m.group("permissions"),
                        last_modified=m.group("last_modified"),
                        size=m.group("size"),
                    )
                )
        return file_list
