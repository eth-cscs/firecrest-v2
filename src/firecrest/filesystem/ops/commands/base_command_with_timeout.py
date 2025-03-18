from abc import abstractmethod
from fastapi import HTTPException, status
from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandErrorHandling,
)
from lib.ssh_clients.ssh_client import BaseCommand


UTILITIES_TIMEOUT = 5


class BaseCommandWithTimeoutErrorHandling(BaseCommandErrorHandling):

    def error_handling(self, stderr: str, exit_status: int):

        error_mess = f"Remote process failed with exit status:{exit_status}"
        if len(stderr) > 0:
            error_mess += f" and error message:{stderr.strip()}"

        if exit_status == 124:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=error_mess
            )

        super().error_handling(stderr, exit_status)


class BaseCommandWithTimeout(BaseCommand, BaseCommandWithTimeoutErrorHandling):

    def __init__(self) -> None:
        super().__init__()

    def get_command(self) -> str:
        return f"timeout {UTILITIES_TIMEOUT}"

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        pass
