# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands

import shlex

from firecrest.filesystem.ops.commands.base_command_with_timeout import (
    BaseCommandWithTimeout,
)


class DdCommand(BaseCommandWithTimeout):

    def __init__(
        self,
        target_path: str = None,
        size: int = None,
        offset: int = 0,
        size_limit: int = None,
        command_timeout: int = 5,
    ) -> None:
        super().__init__(command_timeout=command_timeout)

        self.target_path = target_path
        self.size = size_limit if (size is None or size > size_limit) else size
        self.offset = offset if offset is not None else 0

    def get_command(self) -> str:
        # `offset` may be negative, meaning "this many bytes before EOF".
        # It is resolved against the file size in the same remote command
        # that performs the `dd` read (rather than in a separate `stat`
        # call beforehand), so both values reflect one consistent snapshot
        # of the file even if it is being appended to concurrently.
        #
        # `count=2` brings back 2 chunks of the file, in case the resolved
        # offset is not a multiple of `size`. `parse_output` then trims the
        # result down to the requested window.
        quoted_path = shlex.quote(self.target_path)
        script = (
            f"fsize=$(stat -c%s -- {quoted_path}) || exit 1; "
            f"off={self.offset}; "
            f'if [ "$off" -lt 0 ]; then '
            f"start=$(( fsize + off )); "
            f'if [ "$start" -lt 0 ]; then start=0; fi; '
            f"else start=$off; fi; "
            f"bs={self.size}; skip=$(( start / bs )); "
            f"printf '%s\\n%s\\n' \"$fsize\" \"$start\"; "
            f'dd if={quoted_path} bs="$bs" skip="$skip" count=2 2>/dev/null'
        )
        return f"timeout {self.command_timeout} sh -c {shlex.quote(script)}"

    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        file_size_str, start_str, chunk = stdout.split("\n", 2)
        file_size = int(file_size_str)
        start = int(start_str)

        i = start % self.size
        content = chunk[i : i + self.size]
        end = start + len(content)

        return {
            "content": content,
            "file_size": file_size,
            # Bytes skipped from BOF to reach the start of `content`.
            "start_offset": start,
            # Bytes skipped from EOF to reach the end of `content`,
            # expressed as a negative number (0 means `content` reaches EOF).
            "end_offset": end - file_size,
        }
