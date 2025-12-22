import asyncio
import base64
import click
import http
import json
import signal
import websockets
from enum import Enum
from dataclasses import dataclass, replace
from streamer.streamer_core import ConsoleReporter, stream_receive, stream_send
from websockets.asyncio.server import serve

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB


class Operation(Enum):
    send = "send"
    receive = "receive"


@dataclass
class StreamConfig:
    operation: str
    target: str
    secret: str
    port_range: tuple[int, int]
    ips: list[str]
    host: str
    wait_timeout: int
    inbound_transfer_limit: int


async def stream(config: StreamConfig):
    timeout_handle: asyncio.Handle = None
    reporter = ConsoleReporter()

    def process_request(connection, request):
        nonlocal timeout_handle
        if "Authorization" not in request.headers:
            return connection.respond(
                http.HTTPStatus.UNAUTHORIZED, "Missing Authorization header\n"
            )

        authorization = request.headers["Authorization"]
        if authorization is None:
            return connection.respond(http.HTTPStatus.UNAUTHORIZED, "Missing token\n")

        token = authorization.split("Bearer ")[-1]
        if token is None or token != config.secret:
            return connection.respond(http.HTTPStatus.FORBIDDEN, "Invalid secret\n")

        if timeout_handle:
            timeout_handle.cancel()

    async def server_receive(websocket: websockets.asyncio.server.ServerConnection):
        reporter.info("Client connected.")
        try:
            await stream_receive(
                websocket,
                config.target,
                config.inbound_transfer_limit,
                reporter=reporter,
            )
        except Exception as e:
            reporter.error(f"An error occurred: {e}")
        websocket.server.close()

    async def server_send(websocket):
        reporter.info("Client connected.")
        try:
            await stream_send(websocket, config.target, reporter=reporter)
        except Exception as e:
            reporter.error(f"An error occurred: {e}")
        websocket.server.close()

    start_port, end_port = config.port_range
    for port in range(start_port, end_port + 1):
        try:
            async with serve(
                (
                    server_receive
                    if config.operation == Operation.receive
                    else server_send
                ),
                config.host,
                port,
                max_size=int(
                    CHUNK_SIZE * 1.25
                ),  # Allow some overhead for encoding and headers
                ping_interval=60,
                ping_timeout=None,
                process_request=process_request,
            ) as server:
                reporter.info(f"Server is listening on ws://{config.host}:{port}")
                coordinates = {
                    "ports": [start_port, end_port],
                    "ips": config.ips,
                    "secret": config.secret,
                }
                encoded = base64.urlsafe_b64encode(
                    json.dumps(coordinates).encode("utf-8")
                ).decode("utf-8")

                reporter.info(f"Use these coordinates to connect: {encoded}")

                loop = asyncio.get_running_loop()
                loop.add_signal_handler(signal.SIGTERM, server.close)
                timeout_handle = loop.call_later(config.wait_timeout, server.close)
                await server.wait_closed()
            break
        except OSError:
            reporter.error(f"Server unable to bing on port: {port}")
            continue


@click.group()
@click.option(
    "--secret",
    "_secret",
    help="A shared secret required to initiate the transfer",
    required=True,
)
@click.option(
    "--public-ips",
    "_ips",
    help="A list of public IPs where the streamer server might run.",
    default=["localhost"],
    multiple=True,
)
@click.option(
    "--host",
    "_host",
    help="The interface to use for listening incoming connections",
    default="localhost",
)
@click.option(
    "--port-range",
    "_port_range",
    type=(int, int),
    help="A range of ports to pick from to listen for incoming connections e.g. --port-range 5665 5670",
    default=(5665, 5670),
)
@click.option(
    "--wait-timeout",
    "_wait_timeout",
    help="How long to wait for a connection before exiting (in seconds)",
    default=60 * 60 * 24,  # 24h
)
@click.option(
    "--inbound-transfer-limit",
    "_inbound_transfer_limit",
    help="Limit how much data can be received (in bytes)",
    default=5 * 1024 * 1024 * 1024,  # 5GB
)
@click.pass_context
def server(
    ctx, _secret, _ips, _host, _port_range, _wait_timeout, _inbound_transfer_limit
):
    ctx.ensure_object(dict)
    ctx.obj = StreamConfig(
        operation=None,
        target=None,
        secret=_secret,
        port_range=_port_range,
        ips=_ips,
        host=_host,
        wait_timeout=_wait_timeout,
        inbound_transfer_limit=_inbound_transfer_limit,
    )


@server.command()
@click.option("--path", help="The target path of the file to be sent.", required=True)
@click.pass_context
def send(ctx, path):
    config = replace(ctx.obj, operation=Operation.send, target=path)
    asyncio.run(stream(config))


@server.command()
@click.option(
    "--path", help="The target path of the file to be received.", required=True
)
@click.pass_context
def receive(ctx, path):
    config = replace(ctx.obj, operation=Operation.receive, target=path)
    asyncio.run(stream(config))
