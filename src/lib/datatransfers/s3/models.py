from typing import List, Optional
from pydantic import Field
from lib.datatransfers.datatransfer_base import (
    DataTransferDirective,
    DataTransferOperation,
)


class S3DataTransferDirective(DataTransferDirective):
    download_url: Optional[str] = None
    parts_upload_urls: Optional[List[str]] = None
    complete_upload_url: Optional[str] = None
    max_part_size: Optional[int] = None
    file_name: Optional[str] = Field(
        ..., description="Name of the local file to upload"
    )
    file_size: Optional[int] = Field(
        ..., description="Size of the file to upload in bytes"
    )


class S3DataTransferOperation(DataTransferOperation):
    transfer_directives: S3DataTransferDirective
