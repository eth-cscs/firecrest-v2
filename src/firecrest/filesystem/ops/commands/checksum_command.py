# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from fastapi import status, HTTPException
from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandWithTimeoutErrorHandling,
)
from lib.ssh_clients.ssh_client import BaseCommand

ID = 0
UTILITIES_TIMEOUT = 5

# Available checksum commands
available_algorithms = {
    "SHA256": "sha256sum",  # default
    "SHA224": "sha224sum",
    "SHA384": "sha384sum",
    "SHA512": "sha512sum",
}


class ChecksumCommand(BaseCommand, BaseCommandWithTimeoutErrorHandling):

    def __init__(self, target_path: str = None, algorithm: str = "SHA256") -> None:
        super().__init__()
        self.selected_algorithm = algorithm
        self.target_path = target_path

    def get_command(self) -> str:
        return f"timeout {UTILITIES_TIMEOUT} {available_algorithms[self.selected_algorithm]} -- '{self.target_path}'"

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        # Example of sha256sum output
        # e5b00209ffdf76f4db2895a419bd49cbfdf9350eb9546b73019413a41acd9455  test.dat
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        # Split command'2 output, shall be in 2 parts
        stdout_parts = stdout.split()
        if len(stdout_parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid output: {stdout} {stderr}",
            )
        # Return standard format
        return {
            "algorithm": self.selected_algorithm,
            "checksum": stdout_parts[0],
        }
