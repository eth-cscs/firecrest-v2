from typing import List, Literal, Optional
from pydantic import Field
from lib.datatransfers.datatransfer_base import (
    DataTransferResponse,
    DataTransferRequest,
    DataTransferType,
)


class S3TransferResponse(DataTransferResponse):
    download_url: Optional[str] = None
    parts_upload_urls: Optional[List[str]] = None
    complete_upload_url: Optional[str] = None
    max_part_size: Optional[int] = None
    transfer_method: Literal[DataTransferType.s3,]


class S3TransferRequest(DataTransferRequest):
    file_size: Optional[int] = Field(
        None, description="Size of the file to upload in bytes"
    )
    transfer_method: Literal[DataTransferType.s3,]
