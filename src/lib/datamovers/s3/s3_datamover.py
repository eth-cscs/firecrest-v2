from math import ceil
import uuid
import os
from fastapi import HTTPException
from typing import List
from importlib import resources as imp_resources
from jinja2 import Environment, FileSystemLoader


# storage
from firecrest.filesystem.transfer import scripts

# helpers
from lib.datamovers.datamover_base import (
    DataMoverLocation,
    DataMoverOperation,
    DatamoverBase,
    TransferJob,
    TransferJobLogs,
)

# dependencies
from lib.scheduler_clients.scheduler_base_client import SchedulerBaseClient
from lib.scheduler_clients.slurm.models import SlurmJobDescription


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


async def _generate_presigned_url(
    client,
    action,
    params,
    tenant,
    ttl,
    method=None,
):
    if tenant:
        if "Bucket" in params:
            params["Bucket"] = f"{tenant}:{params['Bucket']}"
    url = await client.generate_presigned_url(
        ClientMethod=action,
        Params=params,
        ExpiresIn=ttl,
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


class S3Datamover(DatamoverBase):

    def __init__(
        self,
        scheduler_client: SchedulerBaseClient,
        directives,
        s3_client_private,
        s3_client_public,
        work_dir,
        bucket_lifecycle_configuration,
        max_part_size,
        tenant,
        ttl,
    ):
        super().__init__(scheduler_client=scheduler_client, directives=directives)
        self.s3_client_private = s3_client_private
        self.s3_client_public = s3_client_public
        self.work_dir = work_dir
        self.bucket_lifecycle_configuration = bucket_lifecycle_configuration
        self.max_part_size = max_part_size
        self.tenant = tenant
        self.ttl = ttl

    async def upload(
        self,
        source: DataMoverLocation,
        target: DataMoverLocation,
        username,
        access_token,
        account,
    ) -> int | None:

        job_id = None
        object_name = f"{str(uuid.uuid4())}/{os.path.basename(target.path)}"

        async with self.s3_client_private:
            try:
                await self.s3_client_private.create_bucket(**{"Bucket": username})
                # Update lifecycle only for new buckets (not throwing the BucketAlreadyOwnedByYou exception)
                await self.s3_client_private.put_bucket_lifecycle_configuration(
                    Bucket=username,
                    LifecycleConfiguration=self.bucket_lifecycle_configuration.to_json(),
                )
            except self.s3_client_private.exceptions.BucketAlreadyOwnedByYou:
                pass

            upload_id = (
                await self.s3_client_private.create_multipart_upload(
                    Bucket=username, Key=object_name
                )
            )["UploadId"]

            post_external_upload_urls = []
            for part_number in range(
                1,
                ceil(source.size / self.max_part_size) + 1,
            ):
                post_external_upload_urls.append(
                    await _generate_presigned_url(
                        self.s3_client_public,
                        "upload_part",
                        {
                            "Bucket": username,
                            "Key": object_name,
                            "UploadId": upload_id,
                            "PartNumber": part_number,
                        },
                        self.tenant,
                        self.ttl,
                    )
                )

            complete_external_multipart_upload_url = await _generate_presigned_url(
                self.s3_client_public,
                "complete_multipart_upload",
                {"Bucket": username, "Key": object_name, "UploadId": upload_id},
                self.tenant,
                self.ttl,
                "POST",
            )

            get_download_url = await _generate_presigned_url(
                self.s3_client_private,
                "get_object",
                {"Bucket": username, "Key": object_name},
                self.tenant,
                self.ttl,
            )

            head_download_url = await _generate_presigned_url(
                self.s3_client_private,
                "head_object",
                {"Bucket": username, "Key": object_name},
                self.tenant,
                self.ttl,
            )

            parameters = {
                "sbatch_directives": _format_directives(self.directives, account),
                "download_head_url": head_download_url,
                "download_url": get_download_url,
                "target_path": target.path,
                "max_part_size": str(self.max_part_size),
            }

            job_script = _build_script("slurm_job_downloader.sh", parameters)
            job = JobHelper(
                f"{self.work_dir}/{username}", job_script, "IngressFileTransfer"
            )

            job_id = await self.scheduler_client.submit_job(
                job_description=SlurmJobDescription(**job.job_param),
                username=username,
                jwt_token=access_token,
            )

        transferJob = TransferJob(
            job_id=job_id,
            system=target.system,
            working_directory=job.working_dir,
            logs=TransferJobLogs(
                output_log=job.job_param["standard_output"],
                error_log=job.job_param["standard_error"],
            ),
        )
        return DataMoverOperation(
            transferJob=transferJob,
            instructions={
                "partsUploadUrls": post_external_upload_urls,
                "completeUploadUrl": complete_external_multipart_upload_url,
                "maxPartSize": self.max_part_size,
            },
        )

    async def download(self) -> int | None:
        pass
