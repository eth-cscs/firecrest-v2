# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands

import shlex

from fastapi import status

from firecrest.filesystem.ops.commands.base_command_error_handling import (
    CommandExecutionError,
)
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
        # `$1`/`$2`/`$3` are passed in as positional arguments below rather
        # than interpolated into the script text, so the path/offset/size
        # values can never be mistaken for shell syntax regardless of how
        # this script is edited in the future.
        script = (
            'fsize=$(stat -c%s -- "$1") || exit 1; '
            'off="$2"; '
            'if [ "$off" -lt 0 ]; then '
            "start=$(( fsize + off )); "
            "else start=$off; fi; "
            'if [ "$start" -lt 0 ]; then start=0; fi; '
            'if [ "$start" -gt "$fsize" ]; then start=$fsize; fi; '
            'bs="$3"; skip=$(( start / bs )); '
            'printf \'%s\\n%s\\n\' "$fsize" "$start"; '
            'dd if="$1" bs="$bs" skip="$skip" count=2'
        )
        quoted_path = shlex.quote(self.target_path)
        return (
            f"{super().get_command()} sh -c {shlex.quote(script)} "
            f"-- {quoted_path} {self.offset} {self.size}"
        )

    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        try:
            file_size_str, start_str, chunk = stdout.split("\n", 2)
            file_size = int(file_size_str)
            start = int(start_str)
        except ValueError as ex:
            error_mess = "Unexpected output format from dd command"
            if stderr:
                error_mess += f", stderr:{stderr.strip()}"
            raise CommandExecutionError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_mess,
            ) from ex

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
