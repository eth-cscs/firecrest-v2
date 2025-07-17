# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
from time import time
from asyncssh import SSHClientProcess
from fastapi import (
    WebSocket,
    WebSocketDisconnect,
    status,
    Path,
    HTTPException,
    Depends,
    Query,
)
from typing import Any, Annotated

# helpers
from lib.helpers.api_auth_helper import ApiAuthHelper


from lib.helpers.router_helper import create_router

# dependencies
from firecrest.dependencies import (
    APIAuthDependency,
    SchedulerClientDependency,
)


# clients
from lib.scheduler_clients.scheduler_base_client import SchedulerBaseClient
from firecrest.compute.models import (
    GetJobMetadataResponse,
    PostJobAttachRequest,
    PostJobSubmissionResponse,
    GetJobResponse,
    PostJobSubmitRequest,
)

router = create_router(
    prefix="/compute/{system_name}/jobs",
    tags=["compute"],
    dependencies=[Depends(APIAuthDependency(authorize=True))],
)

router_ws = create_router(
    prefix="/compute/{system_name}/jobs/{job_id}/attach",
    tags=["compute"],
)


@router.post(
    "",
    description="Submit a new job",
    status_code=status.HTTP_201_CREATED,
    response_model=PostJobSubmissionResponse,
    response_description="Job submitted correctly",
)
async def post_job_submit(
    job_request: PostJobSubmitRequest,
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency()),
    ],
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    job_id = await scheduler_client.submit_job(
        job_description=job_request.job,
        username=username,
        jwt_token=access_token,
    )
    if job_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to submit new job",
        )
    return {"jobId": job_id}


@router.get(
    "",
    description="Get status of all jobs",
    status_code=status.HTTP_200_OK,
    response_model=GetJobResponse,
    response_description="Jobs status returned successfully",
)
async def get_jobs(
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency()),
    ],
    allusers: Annotated[
        bool,
        Query(
            description="If set to `true` returns all jobs visible by the current user, otherwise only the current user owned jobs"
        ),
    ] = False,
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    jobs = await scheduler_client.get_jobs(
        username=username, jwt_token=access_token, allusers=allusers
    )
    return {"jobs": jobs}


@router.get(
    "/{job_id}",
    description="Get status of a job by `{job_id}`",
    status_code=status.HTTP_200_OK,
    response_model=GetJobResponse,
    response_description="Jobs status returned successfully",
)
async def get_job(
    job_id: Annotated[str, Path(description="Job id", pattern="^[a-zA-Z0-9]+$")],
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency()),
    ],
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    jobs = await scheduler_client.get_job(
        job_id=job_id, username=username, jwt_token=access_token
    )
    if jobs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    return {"jobs": jobs}


@router.get(
    "/{job_id}/metadata",
    description="Get metadata of a job by `{job_id}`",
    status_code=status.HTTP_200_OK,
    response_model=GetJobMetadataResponse,
    response_description="Jobs metadata returned successfully",
)
async def get_job_metadata(
    job_id: Annotated[str, Path(description="Job id", pattern="^[a-zA-Z0-9]+$")],
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency()),
    ],
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    jobs = await scheduler_client.get_job_metadata(
        job_id=job_id, username=username, jwt_token=access_token
    )
    if jobs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    return {"jobs": jobs}


@router_ws.websocket("")
async def attach(
    websocket: WebSocket,
    job_id: Annotated[str, Path(description="Job id", pattern="^[a-zA-Z0-9]+$")],
    entrypoint: str,
    token: str,
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency()),
    ],
) -> None:

    # TODO: Refactor authentication dependency to support JWT as query param
    username = "fireuser"  # ApiAuthHelper.get_auth().username
    access_token = token  # ApiAuthHelper.get_access_token()

    await websocket.accept()

    async def read_stdout(process):
        async for line in process.stdout:
            await websocket.send_text(line)

    async def read_stderr(process):
        async for line in process.stderr:
            await websocket.send_text(line)

    async def write_stdin(process):
        while True:
            data = await websocket.receive_text()
            process.stdin.write(data)
            await process.stdin.drain()

    async def keep_alive(process: SSHClientProcess):
        while True:
            process.channel.get_connection().set_extra_info(**{"last_used": time()})
            await asyncio.sleep(5)

    try:
        async with scheduler_client.attach_command_proccess(
            command=entrypoint,
            job_id=None if job_id == "0" else job_id,
            username=username,
            jwt_token=access_token,
        ) as process:
            # Run all tasks concurrently
            stdout_task = asyncio.create_task(read_stdout(process))
            stderr_task = asyncio.create_task(read_stderr(process))
            stdin_task = asyncio.create_task(write_stdin(process))
            keep_alive_task = asyncio.create_task(keep_alive(process))

            # Wait until one of the tasks ends (usually stdin via disconnect)
            done, pending = await asyncio.wait(
                [stdout_task, stderr_task, stdin_task, keep_alive_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()

    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")
        await websocket.close()

    return None


@router.delete(
    "/{job_id}",
    description="Cancel a job",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Job cancelled successfully",
)
async def delete_job_cancel(
    job_id: Annotated[str, Path(description="Job id", pattern="^[a-zA-Z0-9]+$")],
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency()),
    ],
) -> None:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    confirmed = await scheduler_client.cancel_job(
        job_id=job_id, username=username, jwt_token=access_token
    )
    if confirmed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return None
