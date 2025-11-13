from typing import Literal, Optional

from pydantic import Field
from lib.datatransfers.datatransfer_base import (
    DataTransferResponse,
    DataTransferRequest,
    DataTransferType,
)


class WormholeTransferResponse(DataTransferResponse):
    wormhole_code: Optional[str] = Field(default=None, nullable=True)
    transfer_method: Literal[DataTransferType.wormhole,]


class WormholeTransferRequest(DataTransferRequest):
    transfer_method: Literal[DataTransferType.wormhole,]
