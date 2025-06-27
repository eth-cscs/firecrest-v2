from typing import List, Optional
from lib.datatransfers.datatransfer_base import (
    DataTransferOperation,
)


class S3DataTransferOperation(DataTransferOperation):
    download_url: Optional[str] = None
    partsUploadUrls: Optional[List[str]] = None
    completeUploadUrl: Optional[str] = None
    maxPartSize: Optional[int] = None
