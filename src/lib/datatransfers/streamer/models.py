from typing import Literal, Optional

from pydantic import Field
from lib.datatransfers.datatransfer_base import (
    DataTransferResponse,
    DataTransferRequest,
    DataTransferType,
)


class StreamerTransferResponse(DataTransferResponse):
    coordinates: Optional[str] = Field(default=None, nullable=True)
    transfer_method: Literal[DataTransferType.streamer,]


class StreamerTransferRequest(DataTransferRequest):
    transfer_method: Literal[DataTransferType.streamer,]
