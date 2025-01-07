# commands
from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandErrorHandling,
)
from lib.ssh_clients.ssh_client import BaseCommand

UTILITIES_TIMEOUT = 5


class FileCommand(BaseCommand, BaseCommandErrorHandling):

    def __init__(
        self,
        target_path: str = None,
    ) -> None:
        super().__init__()
        self.target_path = target_path

    def get_command(self) -> str:
        return f"timeout {UTILITIES_TIMEOUT} file -b -- '{self.target_path}'"

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):

        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        return stdout.strip()
