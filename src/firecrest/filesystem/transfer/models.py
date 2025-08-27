# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import Any, Optional
from pydantic import Field

# models
from firecrest.filesystem.models import FilesystemRequestBase
from lib.datatransfers.s3.models import S3DataTransferOperation
from lib.models.base_model import CamelModel
from firecrest.filesystem.ops.commands.tar_command import TarCommand


class PostFileUploadRequest(FilesystemRequestBase):
    file_name: str = Field(..., description="Name of the local file to upload")
    account: Optional[str] = Field(
        default=None, description="Name of the account in the scheduler"
    )
    file_size: int = Field(..., description="Size of the file to upload in bytes")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/home/user/dir/file",
                    "file_name": "/path/local/file",
                    "account": "group",
                    "file_size": "7340032",
                }
            ]
        }
    }


class PostFileDownloadRequest(FilesystemRequestBase):
    account: Optional[str] = Field(
        default=None, description="Name of the account in the scheduler"
    )
    model_config = {
        "json_schema_extra": {
            "examples": [{"path": "/home/user/dir/file", "account": "group"}]
        }
    }


class PostXferInternalOperationApiResponse(CamelModel):
    operation: Any


class TransferJobLogs(CamelModel):
    output_log: str
    error_log: str


class TransferJob(CamelModel):
    job_id: int
    system: str
    working_directory: str
    logs: TransferJobLogs


class UploadFileResponse(S3DataTransferOperation):
    pass


class DownloadFileResponse(S3DataTransferOperation):
    pass


class CopyRequest(FilesystemRequestBase):
    target_path: str = Field(..., description="Target path of the copy operation")
    account: Optional[str] = Field(
        default=None, description="Name of the account in the scheduler"
    )
    dereference: Optional[bool] = Field(
        default=False,
        description=(
            "If set to `true`, it follows symbolic links and copies the "
            "files they point to instead of the links themselves."
        ),
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_path": "/home/user/dir/file.orig",
                    "target_path": "/home/user/dir/file.new",
                    "account": "group",
                    "dereference": "true",
                }
            ]
        }
    }


class CopyResponse(CamelModel):
    transfer_job: TransferJob


class DeleteResponse(CamelModel):
    transfer_job: TransferJob


class MoveRequest(FilesystemRequestBase):
    target_path: str = Field(..., description="Target path of the move operation")
    account: Optional[str] = Field(
        default=None, description="Name of the account in the scheduler"
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_path": "/home/user/dir/file.orig",
                    "target_path": "/home/user/dir/file.new",
                    "account": "group",
                }
            ]
        }
    }


class MoveResponse(CamelModel):
    transfer_job: TransferJob


class CompressRequest(FilesystemRequestBase):
    target_path: str = Field(..., description="Target path of the compress operation")
    account: Optional[str] = Field(
        default=None, description="Name of the account in the scheduler"
    )
    match_pattern: Optional[str] = Field(
        default=None, description="Regex pattern to filter files to compress"
    )
    dereference: Optional[bool] = Field(
        default=False,
        description="If set to `true`, it follows symbolic links and archive the files they point to instead of the links themselves.",
    )
    compression: Optional[TarCommand.CompressionType] = Field(
        default="gzip",
        description="Defines the type of compression to be used. By default gzip is used.",
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/home/user/dir",
                    "target_path": "/home/user/file.tar.gz",
                    "match_pattern": "*./[ab].*\\.txt",
                    "dereference": "true",
                    "account": "group",
                    "compression": "none",
                }
            ]
        }
    }


class CompressResponse(CamelModel):
    transfer_job: TransferJob


class ExtractRequest(FilesystemRequestBase):
    target_path: str = Field(
        ..., description="Path to the directory where to extract the compressed file"
    )
    account: Optional[str] = Field(
        default=None, description="Name of the account in the scheduler"
    )
    compression: Optional[TarCommand.CompressionType] = Field(
        default="gzip",
        description="Defines the type of compression to be used. By default gzip is used.",
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_path": "/home/user/dir/file.tar.gz",
                    "target_path": "/home/user/dir",
                    "account": "group",
                    "compression": "none",
                }
            ]
        }
    }


class ExtractResponse(CamelModel):
    transfer_job: TransferJob
