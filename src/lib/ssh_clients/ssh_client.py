# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
from time import time
from typing import Any, Dict
import asyncssh
from asyncssh import ChannelOpenError, ConnectionLost, SSHClientConnection
from contextlib import asynccontextmanager
from abc import ABC, abstractmethod

# clients
from lib.ssh_clients.ssh_key_provider import SSHKeysProvider
from lib.ssh_clients.ssh_keygen_client import SSHKeygenClient
from lib.ssh_clients.ssh_static_keys_provider import SSHStaticKeysProvider


class BaseCommand(ABC):

    @abstractmethod
    def get_command(self) -> str:
        pass

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str, exit_status: int):
        pass


class OutputLimitExceeded(Exception):
    pass


class TimeoutLimitExceeded(Exception):
    pass


class SSHConnectionError(Exception):
    pass


class SSHClient:

    def __init__(
        self,
        conn: SSHClientConnection,
        idle_timeout: int = 60,
        execute_timeout: int = 5,
        keep_alive: int = 5,
        buffer_limit: int = 5 * 1024 * 1024,
    ):
        self.idle_timeout = idle_timeout
        self.conn = conn
        self.conn.set_keepalive(interval=keep_alive, count_max=3)
        self.execute_timeout = execute_timeout
        self.buffer_limit = buffer_limit

    async def _read_limit(self, reader, limit):
        # Note: according to asyncssh author, the following is the
        # suggested approach to limit read buffer.
        # Source: https://github.com/ronf/asyncssh/issues/306#issuecomment-682289651
        try:
            return await reader.readexactly(limit)
        except asyncio.IncompleteReadError as exc:
            return exc.partial

    async def execute(self, command: BaseCommand, stdin: str = None):

        try:
            async with asyncio.timeout(self.execute_timeout):
                process = await self.conn.create_process(command.get_command())

                if stdin:
                    process.stdin.write(stdin)
                    process.stdin.write_eof()

                stdout_data, stdout_error = await asyncio.gather(
                    self._read_limit(process.stdout, self.buffer_limit),
                    self._read_limit(process.stderr, self.buffer_limit),
                )

                if (
                    len(stdout_data) >= self.buffer_limit
                    or len(stdout_error) >= self.buffer_limit
                ):
                    raise OutputLimitExceeded("Command output exceeded buffer limit.")

                process.close()
                await process.wait_closed()
                return command.parse_output(
                    stdout_data, stdout_error, process.exit_status
                )

        except TimeoutError as e:
            raise TimeoutLimitExceeded(
                "Command execution timeout limit exceeded."
            ) from e
        except ConnectionLost as e:
            raise SSHConnectionError("Unable to establish SSH connection.") from e
        except ChannelOpenError as e:
            raise SSHConnectionError("Unable to open a new SSH channel.") from e

    def reset_idle(
        self,
    ) -> None:
        self.conn.set_extra_info(**{"last_used": time()})

    def is_idle(self) -> Any:
        last_used = self.conn.get_extra_info("last_used")
        return (time() - last_used) > self.idle_timeout

    def close(self) -> None:
        self.conn.close()

    def is_closed(self):
        return self.conn.is_closed()


class SSHClientPool:

    lock = asyncio.Lock()

    def __init__(
        self,
        host: str,
        port: int,
        proxy_host: str = None,
        proxy_port: int = None,
        key_provider: SSHKeysProvider = None,
        buffer_limit: int = 5 * 1024 * 1024,
        connect_timeout: int = 5,
        login_timeout: int = 5,
        execute_timeout: int = 5,
        max_clients: int = 100,
        idle_timeout: int = 60,
        keep_alive: int = 5,
    ):
        self.clients: Dict[str, SSHClient] = {}
        assert idle_timeout > execute_timeout
        self.host = host
        self.port = port
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.buffer_limit = buffer_limit
        self.connect_timeout = connect_timeout
        self.login_timeout = login_timeout
        self.execute_timeout = execute_timeout
        self.key_provider = key_provider
        self.conn = None
        self.max_clients = max_clients
        self.idle_timeout = idle_timeout
        self.keep_alive = keep_alive

    def prune_connection_pool(self):
        for client in self.clients.values():
            if client.is_idle():
                client.close()

        # remove closed connections
        self.clients = {
            k: conn for k, conn in self.clients.items() if not conn.is_closed()
        }

    @asynccontextmanager
    async def get_client(self, username: str, jwt_token: str):
        client: SSHClient = None

        try:
            keys = await self.key_provider.get_keys(username, jwt_token)
        except TimeoutError as e:
            raise TimeoutLimitExceeded(
                "SSH keys generation timeout limit exceeded."
            ) from e

        match self.key_provider:
            case SSHKeygenClient():
                sshkey_private = asyncssh.import_private_key(
                    keys["private"], passphrase=keys["passphrase"]
                )
                sshkey_cert_public = asyncssh.import_certificate(keys["public"])
                options = asyncssh.SSHClientConnectionOptions(
                    username=username,
                    client_keys=[sshkey_private],
                    client_certs=[sshkey_cert_public],
                    known_hosts=None,
                    connect_timeout=self.connect_timeout,
                    login_timeout=self.login_timeout,
                    window=self.buffer_limit,
                )
            case SSHStaticKeysProvider():
                sshkey_private = asyncssh.import_private_key(
                    keys["private"], passphrase=keys["passphrase"]
                )
                sshkey_cert_public = ()
                if keys["public"]:
                    sshkey_cert_public = asyncssh.import_certificate(keys["public"])
                options = asyncssh.SSHClientConnectionOptions(
                    username=username,
                    client_keys=[sshkey_private],
                    client_certs=[sshkey_cert_public],
                    known_hosts=None,
                    connect_timeout=self.connect_timeout,
                    login_timeout=self.login_timeout,
                    window=self.buffer_limit,
                )
            case _:
                raise TypeError("Unsupported SSHKeysProvider")

        async with SSHClientPool.lock:
            try:
                if username in self.clients:
                    client = self.clients[username]
                    if client.is_closed():
                        del self.clients[username]
                        client = None

                if client is None:
                    if len(self.clients) >= self.max_clients:
                        raise SSHConnectionError(
                            "SSH connection pool capacity exceeded"
                        )

                    proxy = ()
                    if self.proxy_host:
                        proxy = await asyncssh.connect(
                            host=self.proxy_host, port=self.proxy_port, options=options
                        )

                    conn = await asyncssh.connect(
                        host=self.host, port=self.port, options=options, tunnel=proxy
                    )

                    client = SSHClient(
                        conn,
                        idle_timeout=self.idle_timeout,
                        execute_timeout=self.execute_timeout,
                        buffer_limit=self.buffer_limit,
                        keep_alive=self.keep_alive,
                    )
                    self.clients[username] = client

                client.reset_idle()
                yield client
            except TimeoutError as e:
                raise TimeoutLimitExceeded(
                    "SSH connection timeout limit exceeded."
                ) from e
            except ConnectionResetError as e:
                raise SSHConnectionError("Unable to establish SSH connection.") from e
            except ConnectionLost as e:
                raise SSHConnectionError("Unable to establish SSH connection.") from e
