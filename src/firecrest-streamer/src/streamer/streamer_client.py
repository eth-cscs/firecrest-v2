import asyncio
import base64
import click
import json
import websockets
from dataclasses import dataclass
from typing import Optional, List
from streamer.streamer_core import (
    ConsoleReporter,
    LoggingReporter,
    StreamReporter,
    stream_send,
    stream_receive,
)

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB


@dataclass
class ClientConfig:
    target: str
    port_range: List[int]
    ip_list: List[str]
    secret: str


async def client_receive(
    config: ClientConfig, reporter: Optional[StreamReporter] = None
):
    reporter = reporter or LoggingReporter()
    try:
        for ip in config.ip_list:
            for port in range(config.port_range[0], config.port_range[1] + 1):
                uri = f"ws://{ip}:{port}"
                try:
                    async with websockets.connect(
                        uri,
                        max_size=int(
                            CHUNK_SIZE * 1.25
                        ),  # Allow some overhead for encoding and headers
                        ping_interval=60,
                        ping_timeout=None,
                        additional_headers={"Authorization": f"Bearer {config.secret}"},
                    ) as websocket:
                        await stream_receive(
                            websocket, config.target, reporter=reporter
                        )
                        return
                except (
                    OSError,
                    websockets.exceptions.InvalidStatus,
                    websockets.exceptions.InvalidMessage,
                ):
                    continue
        reporter.error("Unable to establish connection to any provided IPs/ports.")
    except Exception as e:
        reporter.error(f"An error occurred: {e}")
        return


async def client_send(config: ClientConfig, reporter: Optional[StreamReporter] = None):
    reporter = reporter or LoggingReporter()
    try:
        for ip in config.ip_list:
            for port in range(config.port_range[0], config.port_range[1] + 1):
                uri = f"ws://{ip}:{port}"
                try:
                    async with websockets.connect(
                        uri,
                        max_size=int(
                            CHUNK_SIZE * 1.25
                        ),  # Allow some overhead for encoding and headers
                        ping_interval=60,
                        ping_timeout=None,
                        additional_headers={"Authorization": f"Bearer {config.secret}"},
                    ) as websocket:
                        await stream_send(websocket, config.target, reporter=reporter)
                        return
                except (
                    OSError,
                    websockets.exceptions.InvalidStatus,
                    websockets.exceptions.InvalidMessage,
                ):
                    continue
        reporter.error("Unable to establish connection to any provided IPs/ports.")
    except Exception as e:
        reporter.error(f"An error occurred: {e}")
        return


def set_coordinates(coordinates) -> ClientConfig:
    try:
        json_str = base64.urlsafe_b64decode(coordinates).decode("utf-8")
        data = json.loads(json_str)

        return ClientConfig(
            target="",
            secret=data["secret"],
            port_range=data["ports"],
            ip_list=data["ips"],
        )
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
    config = set_coordinates(coordinates)
    config.target = path
    asyncio.run(client_send(config, reporter=ConsoleReporter()))


@click.command()
@click.option(
    "--coordinates",
    help="Secret coordinates used to establish a connection",
    required=True,
)
@click.option("--path", help="The target path of the incoming file.", required=True)
def receive(path, coordinates):
    config = set_coordinates(coordinates)
    config.target = path
    asyncio.run(client_receive(config, reporter=ConsoleReporter()))
