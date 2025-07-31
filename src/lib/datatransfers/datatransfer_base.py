from abc import ABC, abstractmethod
from typing import Optional

from lib.models.base_model import CamelModel
from lib.scheduler_clients.scheduler_base_client import SchedulerBaseClient


class TransferJobLogs(CamelModel):
    output_log: str
    error_log: str


class TransferJob(CamelModel):
    job_id: int
    system: str
    working_directory: str
    logs: TransferJobLogs


class DataTransferLocation(CamelModel):
    host: Optional[str] = None
    system: Optional[str] = None
    path: Optional[str] = None
    size: Optional[int] = None


class DataTransferOperation(CamelModel):
    transfer_job: TransferJob


class DataTransferBase(ABC):

    def __init__(
        self,
        scheduler_client: SchedulerBaseClient,
        directives,
    ):
        self.scheduler_client = scheduler_client
        self.directives = directives

    @abstractmethod
    async def upload(
        self,
        source: DataTransferLocation,
        target: DataTransferLocation,
    ) -> DataTransferOperation | None:
        pass

    @abstractmethod
    async def download(self) -> DataTransferOperation | None:
        pass
