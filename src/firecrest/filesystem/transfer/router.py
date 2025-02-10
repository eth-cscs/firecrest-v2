# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from math import ceil
import uuid
import os
from fastapi import Depends, Path, Query, status, HTTPException
from typing import Annotated, Any, List, Optional
from importlib import resources as imp_resources
from jinja2 import Environment, FileSystemLoader


# plugins
from firecrest.config import HPCCluster, HealthCheckType
from firecrest.filesystem.ops.commands.stat_command import StatCommand
from firecrest.plugins import settings

# storage
from firecrest.filesystem.transfer import scripts

# helpers
from lib.helpers.api_auth_helper import ApiAuthHelper
from lib.helpers.router_helper import create_router

# dependencies
from firecrest.dependencies import (
    APIAuthDependency,
    S3ClientConnectionType,
    S3ClientDependency,
    SSHClientDependency,
    SchedulerClientDependency,
    ServiceAvailabilityDependency,
)

# clients
from lib.scheduler_clients.slurm.slurm_rest_client import SlurmRestClient

# models
from lib.scheduler_clients.slurm.models import SlurmJobDescription
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
    ExtractResponse
)
from lib.ssh_clients.ssh_client import SSHClientPool


router = create_router(
    prefix="/{system_name}/transfer",
    tags=["filesystem"],
    dependencies=[Depends(APIAuthDependency(authorize=True))],
)


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
        loader=FileSystemLoader(imp_resources.files(scripts)),
        autoescape=True
        )
    script_template = script_environment.get_template(filename)

    script_code = script_template.render(parameters)

    return script_code


async def _generate_presigned_url(client, action, params, method=None):
    if settings.storage.tenant:
        if "Bucket" in params:
            params["Bucket"] = f"{settings.storage.tenant}:{params['Bucket']}"
    url = await client.generate_presigned_url(
        ClientMethod=action,
        Params=params,
        ExpiresIn=settings.storage.ttl,
        HttpMethod=method,
    )
    return url


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
    status_code=status.HTTP_201_CREATED,
    response_model=UploadFileResponse,
    response_description="Upload operation",
)
async def post_upload(
    upload_request: PostFileUploadRequest,
    system_name: Annotated[str, Path(description="Target system")],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
    scheduler_client: SlurmRestClient = Depends(SchedulerClientDependency()),
    s3_client_private=Depends(
        S3ClientDependency(connection=S3ClientConnectionType.private)
    ),
    s3_client_public=Depends(
        S3ClientDependency(connection=S3ClientConnectionType.public)
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()

    job_id = None
    object_name = f"{str(uuid.uuid4())}/{upload_request.file_name}"

    try:
        work_dir = next(
            filesystem.path
            for filesystem in system.file_systems
            if filesystem.default_work_dir
        )
    except StopIteration as e:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        ) from e

    async with s3_client_private:
        try:
            await s3_client_private.create_bucket(**{"Bucket": username})
            # Update lifecycle only for new buckets (not throwing the BucketAlreadyOwnedByYou exception)
            await s3_client_private.put_bucket_lifecycle_configuration(
                Bucket=username,
                LifecycleConfiguration=settings.storage.bucket_lifecycle_configuration.to_json(),
            )
        except s3_client_private.exceptions.BucketAlreadyOwnedByYou:
            pass

        upload_id = (
            await s3_client_private.create_multipart_upload(
                Bucket=username, Key=object_name
            )
        )["UploadId"]

        post_external_upload_urls = []
        for part_number in range(
            1,
            ceil(upload_request.file_size / settings.storage.multipart.max_part_size)
            + 1,
        ):
            post_external_upload_urls.append(
                await _generate_presigned_url(
                    s3_client_public,
                    "upload_part",
                    {
                        "Bucket": username,
                        "Key": object_name,
                        "UploadId": upload_id,
                        "PartNumber": part_number,
                    },
                )
            )

        complete_external_multipart_upload_url = await _generate_presigned_url(
            s3_client_public,
            "complete_multipart_upload",
            {"Bucket": username, "Key": object_name, "UploadId": upload_id},
            "POST",
        )

        get_download_url = await _generate_presigned_url(
            s3_client_private, "get_object", {"Bucket": username, "Key": object_name}
        )

        head_download_url = await _generate_presigned_url(
            s3_client_private, "head_object", {"Bucket": username, "Key": object_name}
        )

        parameters = {
            "sbatch_directives": _format_directives(
                system.datatransfer_jobs_directives, upload_request.account
            ),
            "download_head_url": head_download_url,
            "download_url": get_download_url,
            "target_path": f"{upload_request.path}/{upload_request.file_name}",
            "max_part_size": str(settings.storage.multipart.max_part_size),
        }

        job_script = _build_script("slurm_job_downloader.sh", parameters)
        job = JobHelper(f"{work_dir}/{username}", job_script, "IngressFileTransfer")

        job_id = await scheduler_client.submit_job(
            job_description=SlurmJobDescription(**job.job_param),
            username=username,
            jwt_token=access_token,
        )

    return {
        "partsUploadUrls": post_external_upload_urls,
        "completeUploadUrl": complete_external_multipart_upload_url,
        "maxPartSize": settings.storage.multipart.max_part_size,
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
    "/download",
    status_code=status.HTTP_201_CREATED,
    response_model=DownloadFileResponse,
    response_description="Download operation",
)
async def post_download(
    download_request: PostFileDownloadRequest,
    system_name: Annotated[str, Path(description="System where the jobs are running")],
    ssh_client: Annotated[
        SSHClientPool,
        Path(alias="system_name", description="Target system"),
        Depends(SSHClientDependency()),
    ],
    system: HPCCluster = Depends(
        ServiceAvailabilityDependency(service_type=HealthCheckType.filesystem),
        use_cache=False,
    ),
    scheduler_client: SlurmRestClient = Depends(SchedulerClientDependency()),
    s3_client_private=Depends(
        S3ClientDependency(connection=S3ClientConnectionType.private)
    ),
    s3_client_public=Depends(
        S3ClientDependency(connection=S3ClientConnectionType.public)
    ),
) -> Any:
    username = ApiAuthHelper.get_auth().username
    access_token = ApiAuthHelper.get_access_token()

    job_id = None
    object_name = f"{download_request.path.split('/')[-1]}_{str(uuid.uuid4())}"

    try:
        work_dir = next(
            filesystem.path
            for filesystem in system.file_systems
            if filesystem.default_work_dir
        )
    except StopIteration as e:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        ) from e

    stat = StatCommand(download_request.path, True)
    async with ssh_client.get_client(username, access_token) as client:
        stat_output = await client.execute(stat)

    async with s3_client_private:
        try:
            await s3_client_private.create_bucket(**{"Bucket": username})
            # Update lifecycle only for new buckets (not throwing the BucketAlreadyOwnedByYou exception)
            await s3_client_private.put_bucket_lifecycle_configuration(
                Bucket=username,
                LifecycleConfiguration=settings.storage.bucket_lifecycle_configuration.to_json(),
            )
        except s3_client_private.exceptions.BucketAlreadyOwnedByYou:
            pass
        upload_id = (
            await s3_client_private.create_multipart_upload(
                Bucket=username, Key=object_name
            )
        )["UploadId"]

        post_upload_urls = []
        for part_number in range(
            1,
            ceil(stat_output["size"] / settings.storage.multipart.max_part_size) + 1,
        ):
            post_upload_urls.append(
                await _generate_presigned_url(
                    s3_client_private,
                    "upload_part",
                    {
                        "Bucket": username,
                        "Key": object_name,
                        "UploadId": upload_id,
                        "PartNumber": part_number,
                    },
                )
            )

        complete_multipart_url = await _generate_presigned_url(
            s3_client_private,
            "complete_multipart_upload",
            {"Bucket": username, "Key": object_name, "UploadId": upload_id},
            "POST",
        )

        parameters = {
            "sbatch_directives": _format_directives(
                system.datatransfer_jobs_directives, download_request.account
            ),
            "F7T_MAX_PART_SIZE": str(settings.storage.multipart.max_part_size),
            "F7T_MP_USE_SPLIT": (
                "true" if settings.storage.multipart.use_split else "false"
            ),
            "F7T_TMP_FOLDER": f"{settings.storage.multipart.tmp_folder}/{str(uuid.uuid1())}/",
            "F7T_MP_PARALLEL_RUN": str(settings.storage.multipart.parallel_runs),
            "F7T_MP_PARTS_URL": " ".join(f'"{url}"' for url in post_upload_urls),
            "F7T_MP_NUM_PARTS": str(len(post_upload_urls)),
            "F7T_MP_INPUT_FILE": download_request.path,
            "F7T_MP_COMPLETE_URL": complete_multipart_url,
        }

        job = JobHelper(
            f"{work_dir}/{username}",
            _build_script(
                "slurm_job_uploader_multipart.sh",
                parameters,
            ),
            "OutgressFileTransfer",
        )
        get_download_url = None
        job_id = await scheduler_client.submit_job(
            job_description=SlurmJobDescription(**job.job_param),
            username=username,
            jwt_token=access_token,
        )
    async with s3_client_public:
        get_download_url = await _generate_presigned_url(
            s3_client_public,
            "get_object",
            {"Bucket": username, "Key": object_name},
        )
    return {
        "downloadUrl": get_download_url,
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
    "/mv",
    status_code=status.HTTP_201_CREATED,
    response_model=MoveResponse,
    response_description="Move file or directory operation (mv)",
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

    try:
        work_dir = next(
            filesystem.path
            for filesystem in system.file_systems
            if filesystem.default_work_dir
        )
    except StopIteration as e:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        ) from e

    parameters = {
        "sbatch_directives": _format_directives(
            system.datatransfer_jobs_directives, request.account
        ),
        "source_path": request.path,
        "target_path": request.target_path,
    }

    job_script = _build_script("slurm_job_move.sh", parameters)
    job = JobHelper(f"{work_dir}/{username}", job_script, "MoveFiles")

    job_id = await scheduler_client.submit_job(
        job_description=SlurmJobDescription(**job.job_param),
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
    status_code=status.HTTP_201_CREATED,
    response_model=CopyResponse,
    response_description="Copy file or directory operation (cp)",
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
    }

    try:
        work_dir = next(
            filesystem.path
            for filesystem in system.file_systems
            if filesystem.default_work_dir
        )
    except StopIteration as e:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        ) from e

    job_script = _build_script("slurm_job_copy.sh", parameters)

    job = JobHelper(f"{work_dir}/{username}", job_script, "CopyFiles")

    job_id = await scheduler_client.submit_job(
        job_description=SlurmJobDescription(**job.job_param),
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
    status_code=status.HTTP_200_OK,
    response_model=DeleteResponse,
    response_description="Delete file or directory operation (rm)",
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

    try:
        work_dir = next(
            filesystem.path
            for filesystem in system.file_systems
            if filesystem.default_work_dir
        )
    except StopIteration as e:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        ) from e

    parameters = {
        "sbatch_directives": _format_directives(
            system.datatransfer_jobs_directives, account
        ),
        "path": path,
    }
    job_script = _build_script("slurm_job_delete.sh", parameters)
    job = JobHelper(f"{work_dir}/{username}", job_script, "DeleteFiles")

    job_id = await scheduler_client.submit_job(
        job_description=SlurmJobDescription(**job.job_param),
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
    status_code=status.HTTP_201_CREATED,
    response_model=CompressResponse,
    response_description="Compress a file or directory",
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

    try:
        work_dir = next(
            filesystem.path
            for filesystem in system.file_systems
            if filesystem.default_work_dir
        )
    except StopIteration as e:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        ) from e

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
        "pattern": request.pattern,
        "options": options,
    }

    job_script = _build_script("slurm_job_compress.sh", parameters)

    job = JobHelper(f"{work_dir}/{username}", job_script, "CompressFiles")

    job_id = await scheduler_client.submit_job(
        job_description=SlurmJobDescription(**job.job_param),
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
    status_code=status.HTTP_201_CREATED,
    response_model=ExtractResponse,
    response_description="Extract files from a compressed file",
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

    try:
        work_dir = next(
            filesystem.path
            for filesystem in system.file_systems
            if filesystem.default_work_dir
        )
    except StopIteration as e:
        raise ValueError(
            f"The system {system_name} has no filesystem defined as default_work_dir"
        ) from e

    parameters = {
        "sbatch_directives": _format_directives(
            system.datatransfer_jobs_directives, request.account
        ),
        "source_path": request.path,
        "target_path": request.target_path,
    }

    job_script = _build_script("slurm_job_extract.sh", parameters)
    job = JobHelper(f"{work_dir}/{username}", job_script, "CompressFiles")

    job_id = await scheduler_client.submit_job(
        job_description=SlurmJobDescription(**job.job_param),
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
