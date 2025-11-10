import asyncio
import base64
import json
import websockets
import click
from streamer.streamer_core import stream_send, stream_receive

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB


target: str = None
port_range: list[int] = None
ip_list: list[str] = None


async def client_receive():
    global target, scrt, ip_list, port_range
    try:
        for ip in ip_list:
            for port in range(port_range[0], port_range[1] + 1):
                uri = f"ws://{ip}:{port}"
                try:
                    async with websockets.connect(
                        uri,
                        max_size=int(
                            CHUNK_SIZE * 1.25
                        ),  # Allow some overhead for encoding and headers
                        ping_interval=60,
                        ping_timeout=None,
                        additional_headers={"Authorization": f"Bearer {scrt}"},
                    ) as websocket:
                        await stream_receive(websocket, target)
                        return
                except (
                    OSError,
                    websockets.exceptions.InvalidStatus,
                    websockets.exceptions.InvalidMessage,
                ):
                    continue
        print("Unable to establish connection to any provided IPs/ports.")
    except Exception as e:
        print(f"An error occurred: {e}")
        return


async def client_send():
    global target, scrt, ip_list, port_range
    try:
        for ip in ip_list:
            for port in range(port_range[0], port_range[1] + 1):
                uri = f"ws://{ip}:{port}"
                try:
                    async with websockets.connect(
                        uri,
                        max_size=int(
                            CHUNK_SIZE * 1.25
                        ),  # Allow some overhead for encoding and headers
                        ping_interval=60,
                        ping_timeout=None,
                        additional_headers={"Authorization": f"Bearer {scrt}"},
                    ) as websocket:
                        await stream_send(websocket, target)
                        return
                except (
                    OSError,
                    websockets.exceptions.InvalidStatus,
                    websockets.exceptions.InvalidMessage,
                ):
                    continue
        print("Unable to establish connection to any provided IPs/ports.")
    except Exception as e:
        print(f"An error occurred: {e}")
        return


def set_coordinates(coordinates):
    global scrt, port_range, ip_list
    try:
        json_str = base64.urlsafe_b64decode(coordinates).decode("utf-8")
        data = json.loads(json_str)

        scrt = data["secret"]
        port_range = data["ports"]
        ip_list = data["ips"]
    except (json.JSONDecodeError, KeyError, base64.binascii.Error) as e:
        raise click.ClickException("Invalid coordinates format") from e


@click.command()
@click.option("--path", help="The source path of the file to be sent.", required=True)
@click.option(
    "--coordinates",
    help="Secret coordinates used to establish a connection",
    required=True,
)
def send(path, coordinates):
    global target
    set_coordinates(coordinates)
    target = path
    asyncio.run(client_send())


@click.command()
@click.option(
    "--coordinates",
    help="Secret coordinates used to establish a connection",
    required=True,
)
@click.option("--path", help="The target path of the incoming file.", required=True)
def receive(path, coordinates):
    global operation, target
    set_coordinates(coordinates)
    target = path
    asyncio.run(client_receive())
