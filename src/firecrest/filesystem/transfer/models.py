# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import Any, Optional, Union
from pydantic import Field

# models
from firecrest.filesystem.models import FilesystemRequestBase
from lib.datatransfers.datatransfer_base import DataTransferOperation
from lib.datatransfers.magic_wormhole.models import (
    WormholeTransferRequest,
    WormholeTransferResponse,
)
from lib.datatransfers.s3.models import S3TransferRequest, S3TransferResponse
from lib.datatransfers.streamer.models import (
    StreamerTransferRequest,
    StreamerTransferResponse,
)
from lib.models.base_model import CamelModel
from firecrest.filesystem.ops.commands.tar_command import TarCommand


class PostFileUploadRequest(FilesystemRequestBase):
    transfer_directives: Union[
        WormholeTransferRequest | S3TransferRequest | StreamerTransferRequest
    ] = Field(
        ..., description="Data transfer parameters specific to the transfer method"
    )

    account: Optional[str] = Field(
        default=None, description="Name of the account in the scheduler", nullable=True
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sourcePath": "/home/user/dir/file",
                    "account": "group",
                    "transferDirectives": {
                        "transferMethod": "s3",
                        "fileSize": "7340032",
                    },
                }
            ]
        }
    }


class PostFileDownloadRequest(FilesystemRequestBase):
    transfer_directives: Union[
        WormholeTransferRequest | S3TransferRequest | StreamerTransferRequest
    ] = Field(
        ..., description="Data transfer parameters specific to the transfer method"
    )
    account: Optional[str] = Field(
        default=None, description="Name of the account in the scheduler", nullable=True
    )
    model_config = {
        "json_schema_extra": {
            "examples": [{"sourcePath": "/home/user/dir/file", "account": "group"}]
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


class UploadFileResponse(DataTransferOperation):
    transfer_directives: Union[
        WormholeTransferResponse | S3TransferResponse | StreamerTransferResponse
    ] = Field(
        ..., description="Data transfer parameters specific to the transfer method"
    )


class DownloadFileResponse(DataTransferOperation):
    transfer_directives: Union[
        WormholeTransferResponse | S3TransferResponse | StreamerTransferResponse
    ] = Field(
        ..., description="Data transfer parameters specific to the transfer method"
    )


class CopyRequest(FilesystemRequestBase):
    target_path: str = Field(..., description="Target path of the copy operation")
    account: Optional[str] = Field(
        default=None, description="Name of the account in the scheduler", nullable=True
    )
    dereference: bool = Field(
        default=False,
        description=(
            "If set to `true`, it follows symbolic links and copies the "
            "files they point to instead of the links themselves."
        ),
        nullable=False,
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sourcePath": "/home/user/dir/file.orig",
                    "targetPath": "/home/user/dir/file.new",
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
        default=None, description="Name of the account in the scheduler", nullable=True
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sourcePath": "/home/user/dir/file.orig",
                    "targetPath": "/home/user/dir/file.new",
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
        default=None, description="Name of the account in the scheduler", nullable=True
    )
    match_pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern to filter files to compress",
        nullable=True,
    )
    dereference: bool = Field(
        default=False,
        description="If set to `true`, it follows symbolic links and archive the files they point to instead of the links themselves.",
        nullable=False,
    )
    compression: TarCommand.CompressionType = Field(
        default="gzip",
        description="Defines the type of compression to be used. By default gzip is used.",
        nullable=False,
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sourcePath": "/home/user/dir",
                    "targetPath": "/home/user/file.tar.gz",
                    "matchPattern": "*./[ab].*\\.txt",
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
        default=None, description="Name of the account in the scheduler", nullable=True
    )
    compression: TarCommand.CompressionType = Field(
        default="gzip",
        description="Defines the type of compression to be used. By default gzip is used.",
        nullable=False,
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sourcePath": "/home/user/dir/file.tar.gz",
                    "targetPath": "/home/user/dir",
                    "account": "group",
                    "compression": "none",
                }
            ]
        }
    }


class ExtractResponse(CamelModel):
    transfer_job: TransferJob
