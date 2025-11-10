import hashlib
import json
import os

import websockets


CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB


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


async def stream_send(websocket, target):
    try:
        with open(target, "rb") as f:
            file_size = os.stat(target).st_size
            num_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
            hash = hashlib.new("sha256")
            try:
                await websocket.send(
                    json.dumps(
                        {
                            "type": "init",
                            "num_chunks": num_chunks,
                            "file_size": file_size,
                        }
                    ).encode(encoding="utf-8")
                )
                print(f"Transfering {sizeof_fmt(file_size)}...")
                chunk_count = 0
                while chunk := f.read(CHUNK_SIZE):
                    await websocket.send(chunk, text=False)
                    hash.update(chunk)
                    chunk_count += 1
                    printProgressBar(chunk_count, num_chunks, length=40)
                await websocket.send(
                    json.dumps({"type": "eof", "sha256_hash": hash.hexdigest()}).encode(
                        encoding="utf-8"
                    )
                )
                print(f"File {target} sent successfully.")
                return True
            except websockets.exceptions.ConnectionClosedError as e:
                print(f"Remote connection closed with error: {e}")
                return False
    except FileNotFoundError:
        print(f"File {target} not found. Aborting transfer.")
        await websocket.close(
            code=3003,
            reason=json.dumps({"type": "error", "error": "FileNotFoundError"}),
        )
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        await websocket.close(
            code=1011,
            reason=json.dumps({"type": "error", "error": type(e).__name__}),
        )
        return False


async def stream_receive(websocket, target, size_limit=None):
    try:
        init = None
        transfer_size = 0
        with open(target, "xb") as f:
            hash = hashlib.new("sha256")
            chunk_count = 0
            async for message in websocket:
                if init is None:
                    init = json.loads(message.decode("utf-8"))
                    print(f"Transfering {sizeof_fmt(init['file_size'])}...")
                    continue
                if isinstance(message, str) and message.startswith('{"type":"error"'):
                    error = json.loads(message.decode("utf-8"))
                    print(f"A remote error occurred: {error['error']}")
                    break
                if isinstance(message, str) and message.startswith('{"type":"eof"'):
                    if hash.hexdigest() != json.loads(message)["sha256_hash"]:
                        print("Hash mismatch! File transfer corrupted.")
                        os.remove(target)
                    else:
                        print("File received successfully.")
                    break
                transfer_size += CHUNK_SIZE
                if size_limit is not None and transfer_size > size_limit:
                    print(
                        f"Inbound transfer limit exceeded, max allowed transfer size: {size_limit} bytes Aborting transfer."
                    )
                    await websocket.close(
                        code=1009,
                        reason=f"Inbound transfer limit exceeded, max allowed transfer size: {size_limit} bytes.",
                    )
                    os.remove(target)
                    return False
                f.write(message)
                hash.update(message)
                chunk_count += 1
                printProgressBar(chunk_count, init["num_chunks"], length=40)
            print(f"File {target} received successfully.")
            return True
    except FileExistsError:
        print(f"File {target} already exists. Transfer aborted.")
        await websocket.close(
            code=3003,
            reason=json.dumps({"type": "error", "error": "FileNotFoundError"}),
        )
        return False
    except Exception as e:
        print(f"An error occurred: {e}.")
        await websocket.close(
            code=1011,
            reason=json.dumps({"type": "error", "error": type(e).__name__}),
        )
        return False
