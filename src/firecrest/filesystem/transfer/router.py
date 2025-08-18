# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import uuid
import os
from fastapi import Depends, Path, Query, status, HTTPException
from typing import Annotated, Any, List, Optional
from importlib import resources as imp_resources
from jinja2 import Environment, FileSystemLoader


# plugins
from firecrest.config import HPCCluster, HealthCheckType
from firecrest.plugins import settings

# storage
from firecrest.filesystem.transfer import scripts

# helpers
from lib.datatransfers.datatransfer_base import DataTransferLocation
from lib.helpers.api_auth_helper import ApiAuthHelper
from lib.helpers.router_helper import create_router

# dependencies
from firecrest.dependencies import (
    APIAuthDependency,
    DataTransferDependency,
    SchedulerClientDependency,
    ServiceAvailabilityDependency,
)

# clients
from lib.scheduler_clients.slurm.slurm_rest_client import SlurmRestClient

# models
from lib.scheduler_clients.models import JobDescriptionModel
from firecrest.filesystem.transfer.models import (
    DeleteResponse,
    MoveResponse,
    CopyRequest,
    CopyResponse,
    MoveRequest,
    UploadFileResponse,
    PostFileDownloadRequest,
    PostFileUploadRequest,
    DownloadFileResponse,
    TransferJob,
    TransferJobLogs,
    CompressRequest,
    CompressResponse,
    ExtractRequest,
    ExtractResponse,
)


router = create_router(
    prefix="/{system_name}/transfer",
    tags=["filesystem"],
    dependencies=[Depends(APIAuthDependency(authorize=True))],
)

OPS_SIZE_LIMIT = 5 * 1024 * 1024
if settings.storage:
    OPS_SIZE_LIMIT = settings.storage.max_ops_file_size


class JobHelper:
    job_param = None
    working_dir: str = None

    def __init__(
        self,
        working_dir: str = None,
        script: str = None,
        job_name: str = None,
    ):
        self.working_dir = working_dir
        unique_id = uuid.uuid4()
        self.job_param = {
            "name": job_name,
            "working_directory": working_dir,
            "standard_input": "/dev/null",
            "standard_output": f"{working_dir}/.f7t_file_handling_job_{unique_id}.log",
            "standard_error": f"{working_dir}/.f7t_file_handling_job_error_{unique_id}.log",
            "env": {"PATH": "/bin:/usr/bin/:/usr/local/bin/"},
            "script": script,
        }


def _build_script(filename: str, parameters):

    script_environment = Environment(
        loader=FileSystemLoader(imp_resources.files(scripts)), autoescape=True
    )
    script_template = script_environment.get_template(filename)

    script_code = script_template.render(parameters)

    return script_code


def _format_directives(directives: List[str], account: str):

    directives_str = "\n".join(directives)
    if "{account}" in directives_str:
        if account is None:
            raise HTTPException(
                status_code=400, detail="Account parameter is required on this system."
            )
        directives_str = directives_str.format(account=account)

    return directives_str


@router.post(
    "/upload",
    description=f"Create asynchronous upload operation (for files larger than {OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadFileResponse,
    response_description="Upload operation created successfully",
    response_model_exclude_none=True,
)
async def post_upload(
    upload_request: PostFileUploadRequest,
    system_name: Annotated[str, Path(description="Target system")],
    datatransfer=Depends(DataTransferDependency()),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()

    source = DataTransferLocation(
        host=None, system=None, path=None, size=upload_request.file_size
    )
    target = DataTransferLocation(
        host=None,
        system=system_name,
        path=f"{upload_request.path}/{upload_request.file_name}",
        size=upload_request.file_size,
    )

    return await datatransfer.upload(
        source=source,
        target=target,
        username=username,
        access_token=access_token,
        account=upload_request.account,
    )


@router.post(
    "/download",
    description=f"Create asynchronous download operation (for files larger than {OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_201_CREATED,
    response_model=DownloadFileResponse,
    response_description="Download operation created successfully",
    response_model_exclude_none=True,
)
async def post_download(
    download_request: PostFileDownloadRequest,
    system_name: Annotated[str, Path(description="System where the jobs are running")],
    datatransfer=Depends(DataTransferDependency()),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()

    source = DataTransferLocation(
        host=None,
        system=system_name,
        path=download_request.path,
        size=None,
    )
    target = DataTransferLocation(
        host=None,
        system=None,
        path=None,
        size=None,
    )

    return await datatransfer.download(
        source=source,
        target=target,
        username=username,
        access_token=access_token,
        account=download_request.account,
    )


@router.post(
    "/mv",
    description=f"Create move file or directory operation (`mv`) (for files larger than {OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_201_CREATED,
    response_model=MoveResponse,
    response_description="Move file or directory operation created successfully",
)
async def move_mv(
    request: MoveRequest,
    system_name: Annotated[str, Path(description="System where the jobs are running")],
    scheduler_client: SlurmRestClient = Depends(SchedulerClientDependency()),
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    job_id = None

    work_dir = next(
        iter([fs.path for fs in system.file_systems if fs.default_work_dir]), None
    )
    if not work_dir:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        )

    parameters = {
        "sbatch_directives": _format_directives(
            system.datatransfer_jobs_directives, request.account
        ),
        "source_path": request.path,
        "target_path": request.target_path,
    }

    job_script = _build_script("job_move.sh", parameters)
    job = JobHelper(f"{work_dir}/{username}", job_script, "MoveFiles")

    job_id = await scheduler_client.submit_job(
        job_description=JobDescriptionModel(**job.job_param),
        username=username,
        jwt_token=access_token,
    )

    return {
        "transferJob": TransferJob(
            job_id=job_id,
            system=system_name,
            working_directory=job.working_dir,
            logs=TransferJobLogs(
                output_log=job.job_param["standard_output"],
                error_log=job.job_param["standard_error"],
            ),
        ),
    }


@router.post(
    "/cp",
    description=f"Create copy file or directory operation (`cp`) (for files larger than {OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_201_CREATED,
    response_model=CopyResponse,
    response_description="Copy file or directory operation created successfully",
)
async def post_cp(
    request: CopyRequest,
    system_name: Annotated[str, Path(description="System where the jobs are running")],
    scheduler_client: SlurmRestClient = Depends(SchedulerClientDependency()),
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:

    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    job_id = None

    parameters = {
        "sbatch_directives": _format_directives(
            system.datatransfer_jobs_directives, request.account
        ),
        "source_path": request.path,
        "target_path": request.target_path,
        "dereference": request.dereference,
    }

    work_dir = next(
        iter([fs.path for fs in system.file_systems if fs.default_work_dir]), None
    )
    if not work_dir:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        )

    job_script = _build_script("job_copy.sh", parameters)

    job = JobHelper(f"{work_dir}/{username}", job_script, "CopyFiles")

    job_id = await scheduler_client.submit_job(
        job_description=JobDescriptionModel(**job.job_param),
        username=username,
        jwt_token=access_token,
    )

    return {
        "transferJob": TransferJob(
            job_id=job_id,
            system=system_name,
            working_directory=job.working_dir,
            logs=TransferJobLogs(
                output_log=job.job_param["standard_output"],
                error_log=job.job_param["standard_error"],
            ),
        ),
    }


@router.delete(
    "/rm",
    description=f"Create remove file or directory operation (`rm`) (for files larger than {OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_200_OK,
    response_model=DeleteResponse,
    response_description="Remove file or directory operation created successfully",
)
async def delete_rm(
    path: Annotated[str, Query(description="The path to delete")],
    system_name: Annotated[str, Path(description="System where the jobs are running")],
    scheduler_client: SlurmRestClient = Depends(SchedulerClientDependency()),
    account: Optional[str] = None,
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:

    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    job_id = None

    work_dir = next(
        iter([fs.path for fs in system.file_systems if fs.default_work_dir]), None
    )
    if not work_dir:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        )

    parameters = {
        "sbatch_directives": _format_directives(
            system.datatransfer_jobs_directives, account
        ),
        "path": path,
    }
    job_script = _build_script("job_delete.sh", parameters)
    job = JobHelper(f"{work_dir}/{username}", job_script, "DeleteFiles")

    job_id = await scheduler_client.submit_job(
        job_description=JobDescriptionModel(**job.job_param),
        username=username,
        jwt_token=access_token,
    )

    return {
        "transferJob": TransferJob(
            job_id=job_id,
            system=system_name,
            working_directory=job.working_dir,
            logs=TransferJobLogs(
                output_log=job.job_param["standard_output"],
                error_log=job.job_param["standard_error"],
            ),
        ),
    }


@router.post(
    "/compress",
    description=f"Create compress file or directory operation (`tar`) (for files larger than {OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_201_CREATED,
    response_model=CompressResponse,
    response_description="Compress file or directory operation created successfully",
)
async def compress(
    request: CompressRequest,
    system_name: Annotated[str, Path(description="System where the jobs are running")],
    scheduler_client: SlurmRestClient = Depends(SchedulerClientDependency()),
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    job_id = None

    work_dir = next(
        iter([fs.path for fs in system.file_systems if fs.default_work_dir]), None
    )
    if not work_dir:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        )

    source_dir = os.path.dirname(request.path)
    source_file = os.path.basename(request.path)

    options = ""
    if request.dereference:
        options += "--dereference"

    parameters = {
        "sbatch_directives": _format_directives(
            system.datatransfer_jobs_directives, request.account
        ),
        "source_dir": source_dir,
        "source_file": source_file,
        "target_path": request.target_path,
        "match_pattern": request.match_pattern,
        "options": options,
    }

    job_script = _build_script("job_compress.sh", parameters)

    job = JobHelper(f"{work_dir}/{username}", job_script, "CompressFiles")

    job_id = await scheduler_client.submit_job(
        job_description=JobDescriptionModel(**job.job_param),
        username=username,
        jwt_token=access_token,
    )

    return {
        "transferJob": TransferJob(
            job_id=job_id,
            system=system_name,
            working_directory=job.working_dir,
            logs=TransferJobLogs(
                output_log=job.job_param["standard_output"],
                error_log=job.job_param["standard_error"],
            ),
        ),
    }


@router.post(
    "/extract",
    description=f"Create extract file operation (`tar`) (for files larger than {OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_201_CREATED,
    response_model=ExtractResponse,
    response_description="Extract file or directory operation created successfully",
)
async def extract(
    request: ExtractRequest,
    system_name: Annotated[str, Path(description="System where the jobs are running")],
    scheduler_client: SlurmRestClient = Depends(SchedulerClientDependency()),
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()
    job_id = None

    work_dir = next(
        iter([fs.path for fs in system.file_systems if fs.default_work_dir]), None
    )
    if not work_dir:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        )

    parameters = {
        "sbatch_directives": _format_directives(
            system.datatransfer_jobs_directives, request.account
        ),
        "source_path": request.path,
        "target_path": request.target_path,
    }

    job_script = _build_script("job_extract.sh", parameters)
    job = JobHelper(f"{work_dir}/{username}", job_script, "CompressFiles")

    job_id = await scheduler_client.submit_job(
        job_description=JobDescriptionModel(**job.job_param),
        username=username,
        jwt_token=access_token,
    )

    return {
        "transferJob": TransferJob(
            job_id=job_id,
            system=system_name,
            working_directory=job.working_dir,
            logs=TransferJobLogs(
                output_log=job.job_param["standard_output"],
                error_log=job.job_param["standard_error"],
            ),
        ),
    }
