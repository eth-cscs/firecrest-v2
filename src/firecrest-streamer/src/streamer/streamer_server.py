import asyncio
import base64
from enum import Enum
import http
import json
import signal
import websockets
from websockets.asyncio.server import serve
import click
from streamer.streamer_core import stream_send, stream_receive

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB


class Operation(Enum):
    send = "send"
    receive = "receive"


operation: Operation = None
target: str = None
secret: str = None
port_range: tuple[int, int] = None
ips: list[str] = None
host: str = None
wait_timeout: int = None
inbound_transfer_limit: int = None
timeout_handle: asyncio.Handle = None


async def server_receive(websocket: websockets.asyncio.server.ServerConnection):
    global operation, target, inbound_transfer_limit
    print("Client connected.")
    try:
        await stream_receive(websocket, target, inbound_transfer_limit)
    except Exception as e:
        print(f"An error occurred: {e}")
    websocket.server.close()


async def server_send(websocket):
    global target
    print("Client connected.")
    try:
        await stream_send(websocket, target)
    except Exception as e:
        print(f"An error occurred: {e}")
    websocket.server.close()


def process_request(connection, request):
    global secret, timeout_handle
    if "Authorization" not in request.headers:
        return connection.respond(
            http.HTTPStatus.UNAUTHORIZED, "Missing Authorization header\n"
        )

    authorization = request.headers["Authorization"]
    if authorization is None:
        return connection.respond(http.HTTPStatus.UNAUTHORIZED, "Missing token\n")

    token = authorization.split("Bearer ")[-1]
    if token is None or token != secret:
        return connection.respond(http.HTTPStatus.FORBIDDEN, "Invalid secret\n")

    timeout_handle.cancel()


async def stream():
    global secret, port_range, ips, host, wait_timeout, timeout_handle
    start_port, end_port = port_range
    for port in range(start_port, end_port + 1):
        try:
            async with serve(
                server_receive if operation == Operation.receive else server_send,
                host,
                port,
                max_size=int(
                    CHUNK_SIZE * 1.25
                ),  # Allow some overhead for encoding and headers
                ping_interval=60,
                ping_timeout=None,
                process_request=process_request,
            ) as server:
                print(f"Server is listening on ws://{host}:{port}")
                coordinates = {
                    "ports": [start_port, end_port],
                    "ips": ips,
                    "secret": secret,
                }
                encoded = base64.urlsafe_b64encode(
                    json.dumps(coordinates).encode("utf-8")
                ).decode("utf-8")

                print(f"Use these coordinates to connect: {encoded}", flush=True)

                loop = asyncio.get_running_loop()
                loop.add_signal_handler(signal.SIGTERM, server.close)
                timeout_handle = loop.call_later(wait_timeout, server.close)
                await server.wait_closed()
            break
        except OSError:
            print(f"Server unable to bing on port: {port}")
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
def server(_secret, _ips, _host, _port_range, _wait_timeout, _inbound_transfer_limit):
    global secret, port_range, ips, wait_timeout, inbound_transfer_limit, host
    secret = _secret
    port_range = _port_range
    ips = _ips
    host = _host
    wait_timeout = _wait_timeout
    inbound_transfer_limit = _inbound_transfer_limit


@server.command()
@click.option("--path", help="The target path of the file to be sent.", required=True)
def send(path):
    global operation, target
    operation = Operation.send
    target = path
    asyncio.run(stream())


@server.command()
@click.option(
    "--path", help="The target path of the file to be received.", required=True
)
def receive(path):
    global operation, target
    operation = Operation.receive
    target = path
    asyncio.run(stream())
