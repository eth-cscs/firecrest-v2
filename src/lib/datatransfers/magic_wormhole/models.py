from typing import Optional
from lib.datatransfers.datatransfer_base import (
    DataTransferLocation,
    DataTransferOperation,
)
from lib.models.base_model import CamelModel


class WormholeDataTransferDirective(CamelModel):
    wormhole_code: Optional[str] = None
    transfer_method: str = None


class WormholeDataTransferOperation(DataTransferOperation):
    transfer_directives: WormholeDataTransferDirective


class WormholeTransferLocation(DataTransferLocation):
    wormhole_code: Optional[str] = None
