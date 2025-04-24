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


class ContentUnit(str, Enum):
    lines = "lines"
    bytes = "bytes"


class File(CamelModel):
    name: str
    type: str
    link_target: Optional[str]
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
    new_filename: Optional[str] = None
    new_permissions: Optional[str] = None
    new_owner: Optional[str] = None


class GetDirectoryLsResponse(CamelModel):
    output: Optional[list[File]]


class GetFileHeadResponse(CamelModel):
    output: Optional[FileContent]


class GetFileTailResponse(CamelModel):
    output: Optional[FileContent]


class GetFileChecksumResponse(CamelModel):
    output: Optional[FileChecksum]


class GetFileTypeResponse(CamelModel):
    output: Optional[str] = Field(example="directory")


class GetFileStatResponse(CamelModel):
    output: Optional[FileStat]


class PatchFileMetadataResponse(CamelModel):
    output: Optional[PatchFile]


class PutFileChmodRequest(FilesystemRequestBase):
    mode: str = Field(..., description="Mode in octal permission format")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/home/user/dir/file.out",
                    "mode": "777"
                }
            ]
        }
    }


class PutFileChmodResponse(CamelModel):
    output: Optional[File]


class PutFileChownRequest(FilesystemRequestBase):
    owner: Optional[str] = Field(default="", description="User name of the new user owner of the file")
    group: Optional[str] = Field(default="", description="Group name of the new group owner of the file")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/home/user/dir/file.out",
                    "owner": "user",
                    "group": "my-group"
                }
            ]
        }
    }


class PutFileChownResponse(CamelModel):
    output: Optional[File]


class PostMakeDirRequest(FilesystemRequestBase):
    parent: Optional[bool] = Field(default=False, description="If set to `true` creates all its parent directories if they do not already exist")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/home/user/dir/newdir",
                    "parent": "true"
                }
            ]
        }
    }


class PostFileSymlinkRequest(FilesystemRequestBase):
    link_path: str = Field(..., description="Path to the new symlink")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/home/user/dir",
                    "link_path": "/home/user/newlink"
                }
            ]
        }
    }


class PostFileSymlinkResponse(CamelModel):
    output: Optional[File]


class GetViewFileResponse(CamelModel):
    output: Optional[str]


class PostMkdirResponse(CamelModel):
    output: Optional[File]


class PostCompressRequest(FilesystemRequestBase):
    target_path: str = Field(..., description="Path to the compressed file")
    match_pattern: Optional[str] = Field(default=None, description="Regex pattern to filter files to compress")
    dereference: Optional[bool] = Field(default=False, description="If set to `true`, it follows symbolic links and archive the files they point to instead of the links themselves.")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/home/user/dir",
                    "target_path": "/home/user/file.tar.gz",
                    "match_pattern": "*./[ab].*\\.txt",
                    "dereference": "true"
                }
            ]
        }
    }


class PostExtractRequest(FilesystemRequestBase):
    target_path: str = Field(..., description="Path to the directory where to extract the compressed file")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/home/user/dir/file.tar.gz",
                    "target_path": "/home/user/dir"
                }
            ]
        }
    }
