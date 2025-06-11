from abc import ABC, abstractmethod
from typing import Dict, Optional

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


class DataMoverLocation(CamelModel):
    host: Optional[str] = None
    system: Optional[str] = None
    path: Optional[str] = None
    size: Optional[int] = None


class DataMoverOperation(CamelModel):
    transferJob: TransferJob
    instructions: Dict[str, any]


class DatamoverBase(ABC):

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
        source: DataMoverLocation,
        target: DataMoverLocation,
    ) -> DataMoverOperation | None:
        pass

    @abstractmethod
    async def download(self) -> DataMoverOperation | None:
        pass
