# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import sys
from fastapi import (
    Depends,
    File,
    HTTPException,
    Path,
    Response,
    UploadFile,
    status,
    Query,
)
from typing import Any, Annotated
from base64 import b64decode, b64encode

# configs
from firecrest.config import HPCCluster, HealthCheckType
from firecrest.filesystem.ops.commands.tar_command import TarCommand
from firecrest.plugins import settings

# dependencies
from firecrest.dependencies import (
    APIAuthDependency,
    SSHClientDependency,
    ServiceAvailabilityDependency,
)

# helpers
from firecrest.filesystem.ops.commands.base64_command import Base64Command
from firecrest.filesystem.ops.commands.file_command import FileCommand
from firecrest.filesystem.ops.commands.rm_command import RmCommand
from firecrest.filesystem.ops.commands.view_command import ViewCommand
from lib.helpers.api_auth_helper import ApiAuthHelper
from lib.helpers.router_helper import create_router

# clients
from lib.ssh_clients.ssh_client import SSHClientPool

# commands
from firecrest.filesystem.ops.commands.ls_command import LsCommand
from firecrest.filesystem.ops.commands.mkdir_command import MkdirCommand
from firecrest.filesystem.ops.commands.checksum_command import ChecksumCommand
from firecrest.filesystem.ops.commands.stat_command import StatCommand
from firecrest.filesystem.ops.commands.head_command import HeadCommand
from firecrest.filesystem.ops.commands.tail_command import TailCommand
from firecrest.filesystem.ops.commands.chmod_command import ChmodCommand
from firecrest.filesystem.ops.commands.chown_command import ChownCommand
from firecrest.filesystem.ops.commands.symlink_command import SymlinkCommand


# models
from firecrest.filesystem.ops.models import (
    GetDirectoryLsResponse,
    GetFileHeadResponse,
    GetFileTailResponse,
    GetFileChecksumResponse,
    GetFileTypeResponse,
    GetFileStatResponse,
    GetViewFileResponse,
    PostCompressRequest,
    PostExtractRequest,
    PostMakeDirRequest,
    PostMkdirResponse,
    PutFileChmodRequest,
    PutFileChmodResponse,
    PutFileChownRequest,
    PutFileChownResponse,
    PostFileSymlinkRequest,
    PostFileSymlinkResponse,
)


router = create_router(
    prefix="/{system_name}/ops",
    tags=["filesystem"],
    dependencies=[Depends(APIAuthDependency(authorize=True))],
)


@router.put(
    "/chmod",
    status_code=status.HTTP_200_OK,
    response_model=PutFileChmodResponse,
    response_description="Change the file mod bits of a given file according to the specified mode (chmod)",
)
async def put_chmod(
    request_model: PutFileChmodRequest,
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
):
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    chmod = ChmodCommand(target_path=request_model.path, mode=request_model.mode)
    async with ssh_client.get_client(
        username=username, jwt_token=access_token
    ) as client:
        output = await client.execute(chmod)
        return {"output": output}


@router.put(
    "/chown",
    status_code=status.HTTP_200_OK,
    response_model=PutFileChownResponse,
    response_description="Changes the user and/or group ownership of a given file (chown)",
)
async def put_chown(
    request_model: PutFileChownRequest,
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
):
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    chown = ChownCommand(
        target_path=request_model.path,
        owner=request_model.owner,
        group=request_model.group,
    )

    async with ssh_client.get_client(
        username=username, jwt_token=access_token
    ) as client:
        output = await client.execute(chown)
        return {"output": output}


@router.get(
    "/ls",
    status_code=status.HTTP_200_OK,
    response_model=GetDirectoryLsResponse,
    response_description="List the contents of the given directory (ls)",
)
async def get_ls(
    path: Annotated[str, Query(description="The path to list")],
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
    show_hidden: Annotated[
        bool, Query(alias="showHidden", description="Show hidden files")
    ] = False,
    numeric_uid: Annotated[
        bool, Query(alias="numericUid", description="List numeric user and group IDs")
    ] = False,
    recursive: Annotated[
        bool, Query(alias="recursive", description="Recursively list files and folders")
    ] = False,
    dereference: Annotated[
        bool,
        Query(
            alias="dereference",
            description="Show information for the file the link references.",
        ),
    ] = False,
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    ls = LsCommand(path, show_hidden, numeric_uid, recursive, dereference)
    async with ssh_client.get_client(username, access_token) as client:
        output = await client.execute(ls)
        return {"output": output}


@router.get(
    "/head",
    status_code=status.HTTP_200_OK,
    response_model=GetFileHeadResponse,
    response_description="Output the first part of file/s (head)",
)
async def get_head(
    path: Annotated[str, Query(description="File path")],
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
    # TODO Should we allow bytes and lines to be strings? The head allows the following:
    #    NUM may have a multiplier suffix: b 512, kB 1000, K 1024, MB
    #    1000*1000, M 1024*1024, GB 1000*1000*1000, G 1024*1024*1024, and
    #    so on for T, P, E, Z, Y, R, Q.  Binary prefixes can be used, too:
    #    KiB=K, MiB=M, and so on.
    file_bytes: Annotated[
        int | None,
        Query(
            alias="bytes",
            description="The output will be the first NUM bytes of each file.",
        ),
    ] = None,
    lines: Annotated[
        int | None,
        Query(
            description="The output will be the first NUM lines of each file.",
        ),
    ] = None,
    skip_trailing: Annotated[
        bool,
        Query(
            alias="skipTrailing",
            description=(
                "The output will be the whole file, without the last NUM "
                "bytes/lines of each file. NUM should be specified in the "
                "respective argument through `bytes` or `lines`."
            ),
        ),
    ] = False,
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    head = HeadCommand(path, file_bytes, lines, skip_trailing)
    if lines and file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only one of `bytes` or `lines` can be specified.",
        )
    async with ssh_client.get_client(username, access_token) as client:
        output = await client.execute(head)

        # The default behaviour of head returns the first 10 lines
        end_position = 10
        if lines is not None:
            end_position = lines if not skip_trailing else -lines
        elif file_bytes is not None:
            end_position = file_bytes if not skip_trailing else -file_bytes

        return {
            "output": {
                "content": output,
                "contentType": "bytes" if file_bytes else "lines",
                "startPosition": 0,
                "endPosition": end_position,
            }
        }


@router.get(
    "/view",
    status_code=status.HTTP_200_OK,
    response_model=GetViewFileResponse,
    response_description="View full file content (up to 5MB files)",
)
async def get_view(
    path: Annotated[str, Query(description="File path")],
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    view = ViewCommand(path)
    async with ssh_client.get_client(username, access_token) as client:
        output = await client.execute(view)
        return {"output": output}


@router.get(
    "/tail",
    status_code=status.HTTP_200_OK,
    response_model=GetFileTailResponse,
    response_description="Output the last part of a file (tail)",
)
async def get_tail(
    path: Annotated[str, Query(description="File path")],
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
    file_bytes: Annotated[
        int | None,
        Query(
            alias="bytes",
            description="The output will be the last NUM bytes of each file.",
        ),
    ] = None,
    lines: Annotated[
        int | None,
        Query(
            description="The output will be the last NUM lines of each file.",
        ),
    ] = None,
    skip_heading: Annotated[
        bool,
        Query(
            alias="skipHeading",
            description=(
                "The output will be the whole file, without the first NUM "
                "bytes/lines of each file. NUM should be specified in the "
                "respective argument through `bytes` or `lines`."
            ),
        ),
    ] = False,
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    tail = TailCommand(path, file_bytes, lines, skip_heading)
    if lines and file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only one of `bytes` or `lines` can be specified.",
        )

    async with ssh_client.get_client(username, access_token) as client:
        output = await client.execute(tail)
        # The default behaviour of tail returns the last 10 lines
        start_position = 10
        if lines is not None:
            start_position = -lines if not skip_heading else lines
        elif file_bytes is not None:
            start_position = -file_bytes if not skip_heading else file_bytes

        return {
            "output": {
                "content": output,
                "contentType": "bytes" if file_bytes else "lines",
                "startPosition": start_position,
                "endPosition": -1,
            }
        }


@router.get(
    "/checksum",
    status_code=status.HTTP_200_OK,
    response_model=GetFileChecksumResponse,
    response_description="Output the checksum of a file (sha256sum)",
)
async def get_checksum(
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    path: Annotated[str, Query(description="Target system")],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()

    checksum = ChecksumCommand(path)
    async with ssh_client.get_client(username, access_token) as client:
        output = await client.execute(checksum)
        return {"output": output}


@router.get(
    "/file",
    status_code=status.HTTP_200_OK,
    response_model=GetFileTypeResponse,
    response_description="Output the type of a file",
)
async def get_file(
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    path: Annotated[str, Query(description="A file or folder path")],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    file = FileCommand(path)
    async with ssh_client.get_client(username, access_token) as client:
        output = await client.execute(file)
        return {"output": output}


@router.get(
    "/stat",
    status_code=status.HTTP_200_OK,
    response_model=GetFileStatResponse,
    response_description="Output the stat of a file",
)
async def get_stat(
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    path: Annotated[str, Query(description="A file or folder path")],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
    dereference: Annotated[bool, Query(description="Follow symbolic links")] = False,
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    stat = StatCommand(path, dereference)
    async with ssh_client.get_client(username, access_token) as client:
        output = await client.execute(stat)
        return {"output": output}


@router.delete(
    "/rm",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Delete file or directory operation (rm)",
)
async def delete_rm(
    path: Annotated[str, Query(description="The path to delete")],
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> None:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    rm = RmCommand(path)
    async with ssh_client.get_client(username, access_token) as client:
        await client.execute(rm)
        return None


@router.post(
    "/mkdir",
    status_code=status.HTTP_201_CREATED,
    response_model=PostMkdirResponse,
    response_description="Create directory operation (mkdir)",
)
async def post_mkdir(
    request_model: PostMakeDirRequest,
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> None:

    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    mkdir = MkdirCommand(target_path=request_model.path, parent=request_model.parent)
    async with ssh_client.get_client(username, access_token) as client:
        output = await client.execute(mkdir)
        return {"output": output}


@router.post(
    "/symlink",
    status_code=status.HTTP_201_CREATED,
    response_model=PostFileSymlinkResponse,
    response_description="Create symlink operation (ln)",
)
async def post_symlink(
    request_model: PostFileSymlinkRequest,
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    symlink = SymlinkCommand(request_model.path, request_model.link_path)
    async with ssh_client.get_client(username, access_token) as client:
        output = await client.execute(symlink)
        return {"output": output}


@router.get(
    "/download",
    status_code=status.HTTP_200_OK,
    response_model=None,
    response_description=f"Download a small file (max {settings.storage.max_ops_file_size if settings.storage else 'undef.'} Bytes)",
)
async def get_download(
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    path: Annotated[str, Query(description="A file to download")],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    base64 = Base64Command(path)
    async with ssh_client.get_client(username, access_token) as client:
        output = await client.execute(base64)
        return Response(
            content=b64decode(output), media_type="application/octet-stream"
        )


@router.post(
    "/upload",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_description=f"Upload a small file (max {settings.storage.max_ops_file_size if settings.storage else 'undef.'} Bytes)",
)
async def post_upload(
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    path: Annotated[
        str, Query(description="Specify path where file should be uploaded.")
    ],
    file: UploadFile = File(...),
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    base64 = Base64Command(f"{path}/{file.filename}", decode=True)

    raw_content = file.file.read()
    if sys.getsizeof(raw_content) > settings.storage.max_ops_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file is too large.",
        )

    # Note about overwrite
    # Providing a setting to control the overwrite behavior is non trivial.
    # To be reliable this setting should be implemented via an atomic operation (no multiple commands)
    # This could be accived by changing the default bash behavior with "set -o noclobber;"
    # The idea is to append "set -o noclobber;" to the bas64 command and relax the ssh wrapper to allow it.

    content = b64encode(raw_content).decode("utf-8")
    async with ssh_client.get_client(username, access_token) as client:
        await client.execute(base64, content)
        return None


@router.post(
    "/compress",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_description="Compress file and folders",
)
async def post_compress(
    request_model: PostCompressRequest,
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    tar = TarCommand(
        request_model.path,
        request_model.target_path,
        request_model.match_pattern,
        request_model.dereference,
        operation=TarCommand.Operation.compress,
    )

    async with ssh_client.get_client(username, access_token) as client:
        await client.execute(tar)
        return None


@router.post(
    "/extract",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_description="Extract tar gzip archives",
)
async def post_extract(
    request_model: PostExtractRequest,
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    tar = TarCommand(
        request_model.path,
        request_model.target_path,
        operation=TarCommand.Operation.extract,
    )

    async with ssh_client.get_client(username, access_token) as client:
        await client.execute(tar)
        return None
