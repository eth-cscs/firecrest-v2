from typing import Optional
from lib.datatransfers.datatransfer_base import (
    DataTransferDirective,
    DataTransferLocation,
    DataTransferOperation,
)


class WormholeDataTransferDirective(DataTransferDirective):
    wormhole_code: Optional[str] = None


class WormholeDataTransferOperation(DataTransferOperation):
    transfer_directives: WormholeDataTransferDirective


class WormholeTransferLocation(DataTransferLocation):
    wormhole_code: Optional[str] = None
