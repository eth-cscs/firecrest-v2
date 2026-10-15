# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands

import shlex
from typing import Optional

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
        target_path: Optional[str] = None,
        size: int = 5 * 1024 * 1024,  # default is 5MB
        offset: int = 0,
        size_limit: Optional[int] = None,
        command_timeout: int = 5,
    ) -> None:
        super().__init__(command_timeout=command_timeout)

        if not target_path:
            raise ValueError("`target_path` is required")

        if size_limit is not None and size > size_limit:
            size = size_limit
        if size <= 0:
            raise ValueError("`size` must be a positive integer")

        self.target_path = target_path
        self.size = size
        self.offset = offset

    def get_command(self) -> str:
        # `offset` may be negative, meaning "this many bytes before EOF".
        # It is resolved against the file size in the same remote command
        # that performs the `dd` read (rather than in a separate `stat`
        # call beforehand), so both values reflect one consistent snapshot
        # of the file even if it is being appended to concurrently.
        #
        # The window is read byte-exact on the remote side (`skip_bytes` /
        # `count_bytes`), and its length `n` is printed alongside the file
        # size and resolved start. The offsets returned to the caller are
        # derived from those numbers only, never from the length of the
        # decoded text: one character can be several bytes, so the two only
        # agree for pure-ASCII files.
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
            'n=$(( fsize - start )); '
            'if [ "$n" -gt "$3" ]; then n=$3; fi; '
            'printf \'%d\\n%d\\n%d\\n\' "$fsize" "$start" "$n"; '
            'dd if="$1" bs=65536 iflag=skip_bytes,count_bytes '
            'skip="$start" count="$n" status=none'
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
            file_size_str, start_str, length_str, content = stdout.split("\n", 3)
            file_size = int(file_size_str)
            start = int(start_str)
            length = int(length_str)
        except ValueError as ex:
            raise CommandExecutionError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected output format from dd command",
            ) from ex

        end = start + length

        return {
            "content": content,
            "file_size": file_size,
            # Bytes skipped from BOF to reach the start of `content`.
            "start_offset": start,
            # Bytes skipped from EOF to reach the end of `content`,
            # expressed as a negative number (0 means `content` reaches EOF).
            "end_offset": end - file_size,
        }
