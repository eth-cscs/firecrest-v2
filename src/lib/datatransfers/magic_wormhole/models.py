from typing import Optional
from lib.datatransfers.datatransfer_base import (
    DataTransferLocation,
    DataTransferOperation,
)


class WormholeDataTransferOperation(DataTransferOperation):
    wormhole_code: Optional[str] = None


class WormholeTransferLocation(DataTransferLocation):
    wormhole_code: Optional[str] = None
