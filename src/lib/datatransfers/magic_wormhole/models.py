from typing import Literal, Optional
from lib.datatransfers.datatransfer_base import (
    DataTransferResponse,
    DataTransferRequest,
    DataTransferType,
)


class WormholeTransferResponse(DataTransferResponse):
    wormhole_code: Optional[str] = None
    transfer_method: Literal[DataTransferType.wormhole,]


class WormholeTransferRequest(DataTransferRequest):
    transfer_method: Literal[DataTransferType.wormhole,]
