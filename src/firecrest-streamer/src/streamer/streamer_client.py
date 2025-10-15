import asyncio
import base64
import json
import os
import websockets
import click


CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB


target: str = None
port_range: list[int] = None
ip_list: list[str] = None


# Print iterations progress
def printProgressBar(
    iteration,
    total,
    prefix="",
    suffix="",
    decimals=1,
    length=100,
    fill="█",
    printEnd="\r",
):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + "-" * (length - filledLength)
    print(f"\r{prefix} |{bar}| {percent}% {suffix}", end=printEnd)
    # Print New Line on Complete
    if iteration == total:
        print()


def sizeof_fmt(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


async def stream_receive():
    global target, scrt, ip_list, port_range
    welcome = None
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
                    with open(target, "wb") as f:
                        chunk_count = 0
                        async for message in websocket:
                            if welcome is None:
                                welcome = json.loads(message.decode("utf-8"))
                                print(
                                    f"Transfering {sizeof_fmt(welcome['file_size'])}..."
                                )
                                continue
                            if message == "EOF":
                                break
                            f.write(message)
                            chunk_count += 1
                            printProgressBar(
                                chunk_count, welcome["num_chunks"], length=40
                            )
                    print("File received successfully.")
                    return
            except (
                OSError,
                websockets.exceptions.InvalidStatus,
                websockets.exceptions.InvalidMessage,
            ):
                continue
    print("Unable to establish connection to any provided IPs/ports.")


async def stream_send():
    global target, scrt, ip_list, port_range
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
                    file_size = os.stat(target).st_size
                    num_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
                    print(f"Transfering {sizeof_fmt(file_size)}...")
                    chunk_count = 0
                    with open(target, "rb") as f:
                        while chunk := f.read(CHUNK_SIZE):
                            await websocket.send(chunk, text=False)
                            chunk_count += 1
                            printProgressBar(chunk_count, num_chunks, length=40)
                    await websocket.send("EOF")  # Signal end of file
                    print("File sent successfully.")
                    return
            except (
                OSError,
                websockets.exceptions.InvalidStatus,
                websockets.exceptions.InvalidMessage,
            ):
                continue
    print("Unable to establish connection to any provided IPs/ports.")


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
    asyncio.run(stream_send())


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
    asyncio.run(stream_receive())
