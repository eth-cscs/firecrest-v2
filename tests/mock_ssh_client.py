# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from contextlib import asynccontextmanager
from socket import AF_INET
from typing import List

import asyncssh

from lib.models.base_model import CamelModel
from lib.ssh_clients.ssh_client import BaseCommand, SSHClient, SSHClientPool


class NoAuthSSHServer(asyncssh.SSHServer):

    def begin_auth(self, username):
        return False


@asynccontextmanager
async def simple_ssh_server(handler, port=0):

    private_key = asyncssh.generate_private_key("ssh-rsa")
    server = await asyncssh.create_server(
        NoAuthSSHServer,
        "localhost",
        0,
        server_host_keys=[private_key],
        process_factory=handler,
    )
    port = next(
        socket.getsockname()[1] for socket in server.sockets if socket.family == AF_INET
    )
    async with server:
        yield port


class MockedCommand(CamelModel):
    stdout: str = ""
    stderr: str = None
    exit_code: int = 0
    command: str = None
    swalllow_stdin: bool = False


class MockedSSHClient(SSHClient):

    def __init__(self, conn):
        super().__init__(conn=conn)


class MockSSHClientPool(SSHClientPool):

    commands: List[MockedCommand] = []

    def __init__(
        self,
        host: str = None,
        port: int = 22,
    ):
        super().__init__(host, port)

    async def handler(self, process: asyncssh.SSHServerProcess):

        for command in self.commands:
            if command.swalllow_stdin:
                await process.stdin.readline()
                break

        for command in self.commands:
            if process.command.find(command.command) >= 0:
                process.stdout.write(command.stdout)
                process.stderr.write(command.stderr)
                process.exit(command.exit_code)
                return

        # command not found throw
        raise ProcessLookupError("Command not found")

    @asynccontextmanager
    async def mocked_output(self, commands: List[MockedCommand]):
        self.commands = commands
        yield
        self.commands.clear()

    @asynccontextmanager
    async def get_client(self, username, jwt_token):
        async with simple_ssh_server(self.handler) as port:
            async with asyncssh.connect(
                host="localhost", port=port, known_hosts=None
            ) as conn:
                yield MockedSSHClient(conn)
