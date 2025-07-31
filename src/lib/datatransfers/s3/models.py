from typing import List, Optional
from lib.datatransfers.datatransfer_base import (
    DataTransferOperation,
)


class S3DataTransferOperation(DataTransferOperation):
    download_url: Optional[str] = None
    parts_upload_urls: Optional[List[str]] = None
    complete_upload_url: Optional[str] = None
    max_part_size: Optional[int] = None
