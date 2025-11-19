from math import ceil
import uuid
import os


# storage
from firecrest.filesystem.ops.commands.stat_command import StatCommand


# helpers
from lib.datatransfers.datatransfer_base import (
    DataTransferLocation,
    DataTransferOperation,
    DataTransferBase,
    JobHelper,
    TransferJob,
    TransferJobLogs,
    _build_script,
    _format_directives,
)

# dependencies
from lib.scheduler_clients.models import JobDescriptionModel
from lib.scheduler_clients.scheduler_base_client import SchedulerBaseClient
from lib.datatransfers.s3.models import S3TransferResponse


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


class S3Datatransfer(DataTransferBase):

    def __init__(
        self,
        scheduler_client: SchedulerBaseClient,
        directives,
        s3_client_private,
        s3_client_public,
        ssh_client,
        work_dir,
        bucket_lifecycle_configuration,
        max_part_size,
        use_split,
        tmp_folder,
        parallel_runs,
        tenant,
        ttl,
        system_name,
    ):
        super().__init__(scheduler_client=scheduler_client, directives=directives)
        self.s3_client_private = s3_client_private
        self.s3_client_public = s3_client_public
        self.ssh_client = ssh_client
        self.work_dir = work_dir
        self.bucket_lifecycle_configuration = bucket_lifecycle_configuration
        self.max_part_size = max_part_size
        self.use_split = use_split
        self.tmp_folder = tmp_folder
        self.parallel_runs = parallel_runs
        self.tenant = tenant
        self.ttl = ttl
        self.system_name = system_name

    async def upload(
        self,
        source: DataTransferLocation,
        target: DataTransferLocation,
        username,
        access_token,
        account,
    ) -> DataTransferOperation | None:

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
                ceil(source.transfer_directives.file_size / self.max_part_size) + 1,
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

            job_script = _build_script("job_s3_downloader.sh", parameters)
            job = JobHelper(
                f"{self.work_dir}/{username}", job_script, "IngressFileTransfer"
            )

            job_id = await self.scheduler_client.submit_job(
                job_description=JobDescriptionModel(**job.job_param),
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
        directives = S3TransferResponse(
            **{
                "partsUploadUrls": post_external_upload_urls,
                "completeUploadUrl": complete_external_multipart_upload_url,
                "maxPartSize": self.max_part_size,
                "transfer_method": "s3",
            }
        )

        return DataTransferOperation(
            transferJob=transferJob, transfer_directives=directives
        )

    async def download(
        self,
        source: DataTransferLocation,
        target: DataTransferLocation,
        username,
        access_token,
        account,
    ) -> DataTransferOperation | None:

        job_id = None

        stat = StatCommand(source.path, True)
        async with self.ssh_client.get_client(username, access_token) as client:
            stat_output = await client.execute(stat)

        object_name = f"{source.path.split('/')[-1]}_{str(uuid.uuid4())}"

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

            post_upload_urls = []
            for part_number in range(
                1,
                ceil(stat_output["size"] / self.max_part_size) + 1,
            ):
                post_upload_urls.append(
                    await _generate_presigned_url(
                        self.s3_client_private,
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

            complete_multipart_url = await _generate_presigned_url(
                self.s3_client_private,
                "complete_multipart_upload",
                {"Bucket": username, "Key": object_name, "UploadId": upload_id},
                self.tenant,
                self.ttl,
                "POST",
            )

            parameters = {
                "sbatch_directives": _format_directives(self.directives, account),
                "F7T_MAX_PART_SIZE": str(self.max_part_size),
                "F7T_MP_USE_SPLIT": ("true" if self.use_split else "false"),
                "F7T_TMP_FOLDER": f"{self.tmp_folder}/{str(uuid.uuid1())}/",
                "F7T_MP_PARALLEL_RUN": str(self.parallel_runs),
                "F7T_MP_PARTS_URL": " ".join(f'"{url}"' for url in post_upload_urls),
                "F7T_MP_NUM_PARTS": str(len(post_upload_urls)),
                "F7T_MP_INPUT_FILE": source.path,
                "F7T_MP_COMPLETE_URL": complete_multipart_url,
            }

            job = JobHelper(
                f"{self.work_dir}/{username}",
                _build_script(
                    "job_s3_uploader_multipart.sh",
                    parameters,
                ),
                "OutgressFileTransfer",
            )
            get_download_url = None
            job_id = await self.scheduler_client.submit_job(
                job_description=JobDescriptionModel(**job.job_param),
                username=username,
                jwt_token=access_token,
            )
        async with self.s3_client_public:
            get_download_url = await _generate_presigned_url(
                self.s3_client_public,
                "get_object",
                {"Bucket": username, "Key": object_name},
                self.tenant,
                self.ttl,
            )

        directives = S3TransferResponse(
            **{"download_url": get_download_url, "transfer_method": "s3"}
        )

        return DataTransferOperation(
            transferJob=TransferJob(
                job_id=job_id,
                system=self.system_name,
                working_directory=job.working_dir,
                logs=TransferJobLogs(
                    output_log=job.job_param["standard_output"],
                    error_log=job.job_param["standard_error"],
                ),
            ),
            transfer_directives=directives,
        )
