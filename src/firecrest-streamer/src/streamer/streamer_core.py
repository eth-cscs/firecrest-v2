import hashlib
import json
import logging
import os
from typing import Optional, Protocol

import websockets


CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB


class StreamReporter(Protocol):
    """Reporter interface to decouple streaming output from stdout."""

    def info(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...

    def progress(
        self,
        current: int,
        total: int,
        prefix: str = "",
        suffix: str = "",
        length: int = 40,
    ) -> None: ...


class LoggingReporter:
    """Default reporter using the Python logging module."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def progress(
        self,
        current: int,
        total: int,
        prefix: str = "",
        suffix: str = "",
        length: int = 40,
    ) -> None:
        # Logging progress as debug avoids log spam when callers do not care.
        percent = 100 * (current / float(total))
        self.logger.debug("%s %.1f%% %s", prefix, percent, suffix)


class ConsoleReporter:
    """Reporter that prints to stdout with a simple progress bar."""

    def info(self, message: str) -> None:
        print(message)

    def warning(self, message: str) -> None:
        print(message)

    def error(self, message: str) -> None:
        print(message)

    def progress(
        self,
        current: int,
        total: int,
        prefix: str = "",
        suffix: str = "",
        length: int = 40,
    ) -> None:
        printProgressBar(current, total, prefix=prefix, suffix=suffix, length=length)


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


async def stream_send(websocket, target, reporter: Optional[StreamReporter] = None):
    reporter = reporter or LoggingReporter()
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
                reporter.info(f"Transfering {sizeof_fmt(file_size)}...")
                chunk_count = 0
                while chunk := f.read(CHUNK_SIZE):
                    await websocket.send(chunk, text=False)
                    hash.update(chunk)
                    chunk_count += 1
                    reporter.progress(chunk_count, num_chunks, length=40)
                await websocket.send(
                    json.dumps({"type": "eof", "sha256_hash": hash.hexdigest()}).encode(
                        encoding="utf-8"
                    )
                )
                reporter.info(f"File {target} sent successfully.")
                return True
            except websockets.exceptions.ConnectionClosedError as e:
                reporter.error(f"Remote connection closed with error: {e}")
                return False
    except FileNotFoundError:
        reporter.error(f"File {target} not found. Aborting transfer.")
        await websocket.close(
            code=3003,
            reason=json.dumps({"type": "error", "error": "FileNotFoundError"}),
        )
        return False
    except Exception as e:
        reporter.error(f"An error occurred: {e}")
        await websocket.close(
            code=1011,
            reason=json.dumps({"type": "error", "error": type(e).__name__}),
        )
        return False


async def stream_receive(
    websocket, target, size_limit=None, reporter: Optional[StreamReporter] = None
):
    reporter = reporter or LoggingReporter()
    try:
        init = None
        transfer_size = 0
        with open(target, "xb") as f:
            hash = hashlib.new("sha256")
            chunk_count = 0
            async for message in websocket:
                if init is None:
                    init = json.loads(message.decode("utf-8"))
                    reporter.info(f"Transfering {sizeof_fmt(init['file_size'])}...")
                    continue
                if isinstance(message, str) and message.startswith('{"type":"error"'):
                    error = json.loads(message.decode("utf-8"))
                    reporter.error(f"A remote error occurred: {error['error']}")
                    break
                if isinstance(message, str) and message.startswith('{"type":"eof"'):
                    if hash.hexdigest() != json.loads(message)["sha256_hash"]:
                        reporter.error("Hash mismatch! File transfer corrupted.")
                        os.remove(target)
                    else:
                        reporter.info("File received successfully.")
                    break
                transfer_size += CHUNK_SIZE
                if size_limit is not None and transfer_size > size_limit:
                    reporter.error(
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
                reporter.progress(chunk_count, init["num_chunks"], length=40)
            reporter.info(f"File {target} received successfully.")
            return True
    except FileExistsError:
        reporter.error(f"File {target} already exists. Transfer aborted.")
        await websocket.close(
            code=3003,
            reason=json.dumps({"type": "error", "error": "FileNotFoundError"}),
        )
        return False
    except Exception as e:
        reporter.error(f"An error occurred: {e}.")
        await websocket.close(
            code=1011,
            reason=json.dumps({"type": "error", "error": type(e).__name__}),
        )
        return False
