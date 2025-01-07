# commands
from firecrest.filesystem.ops.commands.base_command_error_handling import (
    BaseCommandErrorHandling,
)
from firecrest.filesystem.ops.commands.ls_base_command import LsBaseCommand

UTILITIES_TIMEOUT = 5


class ChownCommand(LsBaseCommand, BaseCommandErrorHandling):

    def __init__(
        self, target_path: str = None, owner: str = None, group: str = None
    ) -> None:
        super().__init__(target_path, no_recursion=True)
        self.target_path = target_path
        self.owner = owner
        self.group = group

    def get_command(self) -> str:
        ls_command = super().get_command()
        return f"timeout {UTILITIES_TIMEOUT} chown -v '{self.owner}':'{self.group}' -- '{self.target_path}' && {ls_command}"

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            super().error_handling(stderr, exit_status)

        return super().parse_output(stdout, stderr, exit_status)
