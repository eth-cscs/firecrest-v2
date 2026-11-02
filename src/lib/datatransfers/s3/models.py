from typing import List, Literal, Optional
from pydantic import Field
from lib.models.base_model import CamelModel
from lib.datatransfers.datatransfer_base import (
    DataTransferResponse,
    DataTransferRequest,
    DataTransferType,
)


class S3STSCredentials(CamelModel):
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: str


class S3TransferResponse(DataTransferResponse):
    sts_credentials: Optional[S3STSCredentials] = Field(
        default=None,
        nullable=True,
        description="Temporary credentials restricted to the target bucket",
    )
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
