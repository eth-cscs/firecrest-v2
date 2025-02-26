# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from fastapi import status, Path, HTTPException, Depends
from typing import Any, Annotated

# helpers
from lib.helpers.api_auth_helper import ApiAuthHelper
from lib.helpers.router_helper import create_router

# logs
from lib.loggers.tracing_logs import tracing_log_command

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


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=PostJobSubmissionResponse,
    response_description="Submit a new job",
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
    tracing_log_command(username, 'submit_job', 0 if job_id is not None else status.HTTP_500_INTERNAL_SERVER_ERROR)
    if job_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to submit new job",
        )
    return {"jobId": job_id}


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=GetJobResponse,
    response_description="Get a job",
)
async def get_jobs(
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency()),
    ],
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    jobs = await scheduler_client.get_jobs(username=username, jwt_token=access_token)
    tracing_log_command(username, 'list_jobs', 0)
    return {"jobs": jobs}


@router.get(
    "/{job_id}",
    status_code=status.HTTP_200_OK,
    response_model=GetJobResponse,
    response_description="Get a job",
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
    tracing_log_command(username, 'job_info', 0 if jobs is not None else status.HTTP_404_NOT_FOUND)
    if jobs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    return {"jobs": jobs}


@router.get(
    "/{job_id}/metadata",
    status_code=status.HTTP_200_OK,
    response_model=GetJobMetadataResponse,
    response_description="Get a job metadata",
)
async def get_job_metadata(
    job_id: Annotated[str, Path(description="Job id", pattern="^[a-zA-Z0-9]+$")],
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency(force_cli_client=True)),
    ],
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    jobs = await scheduler_client.get_job_metadata(
        job_id=job_id, username=username, jwt_token=access_token
    )
    tracing_log_command(username, 'job_metadata', 0 if jobs is not None else status.HTTP_404_NOT_FOUND)
    if jobs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    return {"jobs": jobs}


@router.put(
    "/{job_id}/attach",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Attach a procces to a job",
)
async def attach(
    job_id: Annotated[str, Path(description="Job id", pattern="^[a-zA-Z0-9]+$")],
    job_attach: PostJobAttachRequest,
    scheduler_client: Annotated[
        SchedulerBaseClient,
        Path(alias="system_name", description="Target system"),
        Depends(SchedulerClientDependency()),
    ],
) -> None:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    await scheduler_client.attach_command(
        command=job_attach.command,
        job_id=job_id,
        username=username,
        jwt_token=access_token,
    )
    tracing_log_command(username, 'attach_job_process', 0)
    return None


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Cancel the job",
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
    tracing_log_command(username, 'cancel_job', 0 if confirmed is not None else status.HTTP_404_NOT_FOUND)
    if confirmed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return None
