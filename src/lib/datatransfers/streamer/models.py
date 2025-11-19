from typing import Literal, Optional
from lib.datatransfers.datatransfer_base import (
    DataTransferResponse,
    DataTransferRequest,
    DataTransferType,
)


class StreamerTransferResponse(DataTransferResponse):
    coordinates: Optional[str] = None
    transfer_method: Literal[DataTransferType.streamer,]


class StreamerTransferRequest(DataTransferRequest):
    transfer_method: Literal[DataTransferType.streamer,]
