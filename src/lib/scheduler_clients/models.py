# models
from typing import List, Optional
from lib.models import CamelModel


class JobStatus(CamelModel):
    state: str
    stateReason: Optional[str] = None
    exitCode: int
    interruptSignal: Optional[int] = None


class JobTime(CamelModel):
    elapsed: int
    start: Optional[int]
    end: Optional[int]
    suspended: Optional[int]
    limit: int


class JobTask(CamelModel):
    id: str
    name: str
    status: JobStatus
    time: JobTime


class JobModel(CamelModel):
    job_id: int
    name: str
    status: JobStatus
    tasks: Optional[List[JobTask]] = None
    time: JobTime


class JobMetadataModel(CamelModel):
    pass


class JobDescriptionModel(CamelModel):
    pass


class JobSubmitRequestModel(CamelModel):
    pass


class NodeModel(CamelModel):
    pass


class ReservationModel(CamelModel):
    pass


class PartitionModel(CamelModel):
    pass
