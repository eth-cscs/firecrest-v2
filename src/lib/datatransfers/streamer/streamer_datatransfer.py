# helpers
import base64
import json
from lib.datatransfers.datatransfer_base import (
    DataTransferLocation,
    DataTransferOperation,
    DataTransferBase,
    JobHelper,
    StreamerDataTransferDirective,
    TransferJob,
    TransferJobLogs,
    _build_script,
    _format_directives,
)
import secrets
from lib.scheduler_clients.models import JobDescriptionModel
from lib.scheduler_clients.scheduler_base_client import SchedulerBaseClient
from lib.datatransfers.streamer.models import StreamerDataTransferOperation


class StreamerDatatransfer(DataTransferBase):

    def __init__(
        self,
        scheduler_client: SchedulerBaseClient,
        directives,
        work_dir,
        system_name,
        pypi_index_url=None,
        port_range=(50000, 60000),
        public_ips=None,
        host="localhost",
        wait_timeout=60 * 60 * 24,  # 24h
        inbound_transfer_limit=5 * 1024 * 1024 * 1024,  # 5GB
    ):
        super().__init__(scheduler_client=scheduler_client, directives=directives)
        self.work_dir = work_dir
        self.system_name = system_name
        self.pypi_index_url = pypi_index_url
        self.port_range = port_range
        self.public_ips = public_ips if public_ips else ["localhost"]
        self.host = host
        self.wait_timeout = wait_timeout
        self.inbound_transfer_limit = inbound_transfer_limit

    async def upload(
        self,
        source: DataTransferLocation,
        target: DataTransferLocation,
        username,
        access_token,
        account,
    ) -> DataTransferOperation | None:

        job_id = None
        secret = secrets.token_urlsafe(16)
        start_port, end_port = self.port_range
        parameters = {
            "sbatch_directives": _format_directives(self.directives, account),
            "operation": "receive",
            "target_path": target.path,
            "secret": secret,
            "port_range": f"{start_port} {end_port}",
            "public_ips": self.public_ips,
            "host": self.host,
            "pypi_index_url": self.pypi_index_url,
            "wait_timeout": self.wait_timeout,
            "inbound_transfer_limit": self.inbound_transfer_limit,
        }

        job_script = _build_script("job_streamer.sh", parameters)
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

        coordinates = {
            "ports": [start_port, end_port],
            "ips": self.public_ips,
            "secret": secret,
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(coordinates).encode("utf-8")
        ).decode("utf-8")

        directives = StreamerDataTransferDirective(
            **{"coordinates": encoded, "transfer_method": "streamer"}
        )

        return StreamerDataTransferOperation(
            transferJob=transferJob,
            transfer_directives=directives,
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
        secret = secrets.token_urlsafe(16)
        start_port, end_port = self.port_range
        parameters = {
            "sbatch_directives": _format_directives(self.directives, account),
            "operation": "send",
            "target_path": source.path,
            "secret": secret,
            "public_ips": self.public_ips,
            "port_range": f"{start_port} {end_port}",
            "pypi_index_url": self.pypi_index_url,
            "wait_timeout": self.wait_timeout,
            "inbound_transfer_limit": self.inbound_transfer_limit,
        }

        job = JobHelper(
            f"{self.work_dir}/{username}",
            _build_script("job_streamer.sh", parameters),
            "OutgressFileTransfer",
        )

        job_id = await self.scheduler_client.submit_job(
            job_description=JobDescriptionModel(**job.job_param),
            username=username,
            jwt_token=access_token,
        )

        coordinates = {
            "ports": [start_port, end_port],
            "ips": self.public_ips,
            "secret": secret,
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(coordinates).encode("utf-8")
        ).decode("utf-8")

        directives = StreamerDataTransferDirective(
            **{"coordinates": encoded, "transfer_method": "streamer"}
        )

        return StreamerDataTransferOperation(
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
