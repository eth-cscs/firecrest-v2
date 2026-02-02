# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum
from typing import Optional

# models
from firecrest.filesystem.models import FilesystemRequestBase
from lib.models import CamelModel
from pydantic import Field
from firecrest.filesystem.ops.commands.tar_command import TarCommand


class ContentUnit(str, Enum):
    lines = "lines"
    bytes = "bytes"


class File(CamelModel):
    name: str
    type: str
    link_target: Optional[str] = Field(None, nullable=True)
    user: str
    group: str
    permissions: str
    last_modified: str
    size: str


class FileContent(CamelModel):
    content: str
    content_type: ContentUnit
    start_position: int
    end_position: int


class FileChecksum(CamelModel):
    algorithm: str = "SHA-256"
    checksum: str


class FileStat(CamelModel):
    # message: str
    mode: int
    ino: int
    dev: int
    nlink: int
    uid: int
    gid: int
    size: int
    atime: int
    ctime: int
    mtime: int
    # birthtime: int


class PatchFile(CamelModel):
    message: str
    new_filepath: str
    new_permissions: str
    new_owner: str


class PatchFileMetadataRequest(CamelModel):
    new_filename: Optional[str] = Field(None, nullable=True)
    new_permissions: Optional[str] = Field(None, nullable=True)
    new_owner: Optional[str] = Field(None, nullable=True)


class GetDirectoryLsResponse(CamelModel):
    output: Optional[list[File]] = Field(None, nullable=True)


class GetFileHeadResponse(CamelModel):
    output: Optional[FileContent] = Field(None, nullable=True)


class GetFileTailResponse(CamelModel):
    output: Optional[FileContent] = Field(None, nullable=True)


class GetFileChecksumResponse(CamelModel):
    output: Optional[FileChecksum] = Field(None, nullable=True)


class GetFileTypeResponse(CamelModel):
    output: Optional[str] = Field(None, example="directory", nullable=True)


class GetFileStatResponse(CamelModel):
    output: Optional[FileStat] = Field(None, nullable=True)


class PatchFileMetadataResponse(CamelModel):
    output: Optional[PatchFile] = Field(None, nullable=True)


class PutFileChmodRequest(FilesystemRequestBase):
    mode: str = Field(..., description="Mode in octal permission format")
    model_config = {
        "json_schema_extra": {
            "examples": [{"path": "/home/user/dir/file.out", "mode": "777"}]
        }
    }


class PutFileChmodResponse(CamelModel):
    output: Optional[File] = Field(None, nullable=True)


class PutFileChownRequest(FilesystemRequestBase):
    owner: str = Field(
        default="",
        description="User name of the new user owner of the file",
        nullable=False,
    )
    group: str = Field(
        default="",
        description="Group name of the new group owner of the file",
        nullable=False,
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/home/user/dir/file.out",
                    "owner": "user",
                    "group": "my-group",
                }
            ]
        }
    }


class PutFileChownResponse(CamelModel):
    output: Optional[File] = Field(None, nullable=True)


class PostMakeDirRequest(FilesystemRequestBase):
    parent: bool = Field(
        default=False,
        description="If set to `true` creates all its parent directories if they do not already exist",
        nullable=False,
    )
    model_config = {
        "json_schema_extra": {
            "examples": [{"path": "/home/user/dir/newdir", "parent": "true"}]
        }
    }


class PostFileSymlinkRequest(FilesystemRequestBase):
    link_path: str = Field(..., description="Path to the new symlink")
    model_config = {
        "json_schema_extra": {
            "examples": [{"path": "/home/user/dir", "link_path": "/home/user/newlink"}]
        }
    }


class PostFileSymlinkResponse(CamelModel):
    output: Optional[File] = Field(None, nullable=True)


class GetViewFileResponse(CamelModel):
    output: Optional[str] = Field(None, nullable=True)


class PostMkdirResponse(CamelModel):
    output: Optional[File] = Field(None, nullable=True)


class PostCompressRequest(FilesystemRequestBase):
    target_path: str = Field(..., description="Path to the compressed file")
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
                    "compression": "none",
                }
            ]
        }
    }


class PostExtractRequest(FilesystemRequestBase):
    target_path: str = Field(
        ..., description="Path to the directory where to extract the compressed file"
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
                    "compression": "none",
                }
            ]
        }
    }
