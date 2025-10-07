import asyncio
import base64
from enum import Enum
import http
import json
import os
import signal
import websockets
from websockets.asyncio.server import serve
import click


CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB


class Operation(Enum):
    send = "send"
    receive = "receive"


operation: Operation = None
target: str = None
secret: str = None
port_range: tuple[int, int] = None
ip: str = None


async def stream_receive(websocket):
    global operation, target
    print("Client connected.")
    with open(target, "wb") as f:
        try:
            async for message in websocket:
                if message == "EOF":
                    print("File transfer complete.")
                    break
                f.write(message)
        except websockets.ConnectionClosed:
            print("Connection closed unexpectedly.")
    print(f"File {target} received successfully.")
    websocket.server.close()


async def stream_send(websocket):
    global operation, target
    print("Client connected.")
    file_size = os.stat(target).st_size
    num_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    await websocket.send(
        json.dumps({"num_chunks": num_chunks, "file_size": file_size}).encode(
            encoding="utf-8"
        )
    )
    with open(target, "rb") as f:
        try:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                await websocket.send(chunk)
            await websocket.send("EOF")  # signal end of file
        except websockets.ConnectionClosed:
            print("Connection closed unexpectedly.")
    print(f"File {target} sent successfully.")
    websocket.server.close()


def process_request(connection, request):
    global secret
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


async def stream():
    global secret, port_range, ip
    start_port, end_port = port_range
    for port in range(start_port, end_port):
        try:
            async with serve(
                stream_receive if operation == Operation.receive else stream_send,
                ip,
                port,
                max_size=CHUNK_SIZE,
                ping_interval=60,
                ping_timeout=None,
                process_request=process_request,
            ) as server:
                print(f"Server is listening on ws://{ip}:{port}")
                coordinates = {
                    "ports": [start_port, end_port],
                    "ips": [ip],
                    "secret": secret,
                }
                encoded = base64.urlsafe_b64encode(
                    json.dumps(coordinates).encode("utf-8")
                ).decode("utf-8")

                print(f"Use these coordinates to connect: {encoded}")

                loop = asyncio.get_running_loop()
                loop.add_signal_handler(signal.SIGTERM, server.close)
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
    "--ip",
    "_ip",
    help="The IP to use for listening incoming connections",
    default="0.0.0.0",
)
@click.option(
    "--port-range",
    "_port_range",
    type=(int, int),
    help="A range of ports to pick from to listen for incoming connections e.g. --port-range 5665 5670",
    default=(5665, 5670),
)
def server(_secret, _ip, _port_range):
    global secret, port_range, ip
    secret = _secret
    port_range = _port_range
    ip = _ip


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
