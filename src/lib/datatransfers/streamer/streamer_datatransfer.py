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

from lib.scheduler_clients.models import JobDescriptionModel
from lib.datatransfers.magic_wormhole.models import (
    WormholeDataTransferDirective,
    WormholeDataTransferOperation,
)
from lib.scheduler_clients.scheduler_base_client import SchedulerBaseClient


class StreamerDatatransfer(DataTransferBase):

    def __init__(
        self,
        scheduler_client: SchedulerBaseClient,
        directives,
        work_dir,
        system_name,
    ):
        super().__init__(scheduler_client=scheduler_client, directives=directives)
        self.work_dir = work_dir
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

        parameters = {
            "sbatch_directives": _format_directives(self.directives, account),
            "target_path": target.path,
            "streamer_coordinates": source.transfer_directives.streamer_coordinates,
            "pypi_index_url": "https://jfrog.svc.cscs.ch/artifactory/api/pypi/pypi-remote/simple",
        }

        job_script = _build_script("job_streame.sh", parameters)
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
        directives = WormholeDataTransferDirective(**{"transfer_method": "wormhole"})

        return WormholeDataTransferOperation(
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
        wormhole_code = generate_wormhole_code()

        parameters = {
            "sbatch_directives": _format_directives(self.directives, account),
            "source": source.path,
            "wormhole_code": wormhole_code,
            "pypi_index_url": "https://jfrog.svc.cscs.ch/artifactory/api/pypi/pypi-remote/simple",
        }

        job = JobHelper(
            f"{self.work_dir}/{username}",
            _build_script(
                "job_wormhole_send.sh",
                parameters,
            ),
            "OutgressFileTransfer",
        )

        job_id = await self.scheduler_client.submit_job(
            job_description=JobDescriptionModel(**job.job_param),
            username=username,
            jwt_token=access_token,
        )

        directives = WormholeDataTransferDirective(
            **{"wormhole_code": wormhole_code, "transfer_method": "wormhole"}
        )

        return WormholeDataTransferOperation(
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
