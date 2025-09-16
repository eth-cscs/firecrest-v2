from typing import List, Optional
from lib.datatransfers.datatransfer_base import (
    DataTransferDirective,
    DataTransferOperation,
)


class S3DataTransferDirective(DataTransferDirective):
    download_url: Optional[str] = None
    parts_upload_urls: Optional[List[str]] = None
    complete_upload_url: Optional[str] = None
    max_part_size: Optional[int] = None


class S3DataTransferOperation(DataTransferOperation):
    transfer_directives: S3DataTransferDirective
