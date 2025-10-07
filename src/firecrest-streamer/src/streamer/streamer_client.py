import asyncio
import base64
import json
import websockets
import click


CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB


target: str = None
token: str = None
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
                        chunk_count = 0
                        async for message in websocket:
                            if welcome is None:
                                welcome = json.loads(message.decode("utf-8"))
                                print(
                                    f"Transfering {sizeof_fmt(welcome['file_size'])}..."
                                )
                            if message == "EOF":
                                print("File transfer complete.")
                                break
                            f.write(message)
                            printProgressBar(
                                chunk_count, welcome["num_chunks"], length=40
                            )
                            chunk_count += 1
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


def set_auth(token):
    global scrt, port_range, ip_list
    try:
        json_str = base64.urlsafe_b64decode(token).decode("utf-8")
        data = json.loads(json_str)

        scrt = data["secret"]
        port_range = data["ports"]
        ip_list = data["ips"]
    except (json.JSONDecodeError, KeyError, base64.binascii.Error) as e:
        raise click.ClickException("Invalid token format") from e


@click.command()
@click.option(
    "--token", help="A secret token used to establish a connection", required=True
)
@click.option("--path", help="The source path of the file to be sent.", required=True)
def send(path, token):
    global target
    set_auth(token)
    target = path
    asyncio.run(stream_send())


@click.command()
@click.option(
    "--token", help="A secret token used to establish a connection", required=True
)
@click.option("--path", help="The target path of the incoming file.", required=True)
def receive(path, token):
    global operation, target
    set_auth(token)
    target = path
    asyncio.run(stream_receive())
