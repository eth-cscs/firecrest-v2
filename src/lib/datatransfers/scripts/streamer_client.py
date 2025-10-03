import asyncio
import base64
from enum import Enum
import http
import json
import signal
import websockets
from websockets.asyncio.server import serve
import click


CHUNK_SIZE = 1 * 1024 * 1024  # 5 MiB


target: str = None
token: str = None
port_range: list[int] = None
ip_list: list[str] = None


async def stream_receive():
    global target, scrt, ip_list, port_range
    for ip in ip_list:
        for port in range(port_range[0], port_range[1]):
            uri = f"ws://{ip}:{port}"
            try:
                async with websockets.connect(
                    uri,
                    max_size=CHUNK_SIZE,
                    ping_interval=60,
                    ping_timeout=None,
                    additional_headers={"Authorization": f"Bearer {scrt}"},
                ) as websocket:
                    with open(target, "wb") as f:
                        async for message in websocket:
                            if message == "EOF":
                                print("File transfer complete.")
                                break
                            f.write(message)
                    print("File received successfully.")
                    return
            except (OSError, websockets.exceptions.InvalidStatus):
                continue
    print("Unable to establish connection to any provided IPs/ports.")


async def stream_send():
    global target, scrt, ip_list, port_range
    for ip in ip_list:
        for port in range(port_range[0], port_range[1]):
            uri = f"ws://{ip}:{port}"
            try:
                async with websockets.connect(
                    uri,
                    max_size=CHUNK_SIZE,
                    ping_interval=60,
                    ping_timeout=None,
                    additional_headers={"Authorization": f"Bearer {scrt}"},
                ) as websocket:
                    with open(target, "rb") as f:
                        while chunk := f.read(CHUNK_SIZE):
                            await websocket.send(chunk)
                    await websocket.send("EOF")  # Signal end of file
                    print("File sent successfully.")
                    return
            except OSError:
                continue
    print("Unable to establish connection to any provided IPs/ports.")


@click.group()
@click.option(
    "--token", help="A secret token used to establish a connection", required=True
)
def cli(token):
    global scrt, port_range, ip_list
    json_str = base64.urlsafe_b64decode(token).decode("utf-8")
    data = json.loads(json_str)

    scrt = data["secret"]
    port_range = data["ports"]
    ip_list = data["ips"]


@cli.command()
@click.option("--path", help="The source path of the file to be sent.", required=True)
def send(path):
    global target
    target = path
    asyncio.run(stream_send())


@cli.command()
@click.option("--path", help="The target path of the incoming file.", required=True)
def receive(path):
    global operation, target
    target = path
    asyncio.run(stream_receive())


if __name__ == "__main__":
    cli()
