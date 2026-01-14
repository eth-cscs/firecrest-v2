from typing import List, Literal, Optional
from pydantic import Field
from lib.datatransfers.datatransfer_base import (
    DataTransferResponse,
    DataTransferRequest,
    DataTransferType,
)


class S3TransferResponse(DataTransferResponse):
    download_url: Optional[str] = Field(default=None, nullable=True)
    parts_upload_urls: Optional[List[str]] = Field(default=None, nullable=True)
    complete_upload_url: Optional[str] = Field(default=None, nullable=True)
    max_part_size: Optional[int] = Field(default=None, nullable=True)
    transfer_method: Literal[DataTransferType.s3,]


class S3TransferRequest(DataTransferRequest):
    file_size: Optional[int] = Field(
        None, description="Size of the file to upload in bytes", nullable=True
    )
    transfer_method: Literal[DataTransferType.s3,]
