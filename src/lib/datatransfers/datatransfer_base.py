from abc import ABC, abstractmethod
from typing import List, Optional
import uuid
from enum import Enum
from jinja2 import Environment, FileSystemLoader
from importlib import resources as imp_resources
from typing import Literal, Union
from lib.models.base_model import CamelModel
from lib.scheduler_clients.scheduler_base_client import SchedulerBaseClient
from lib.datatransfers import scripts
from fastapi import HTTPException
from pydantic import ConfigDict, Field


class TransferJobLogs(CamelModel):
    output_log: str
    error_log: str


class TransferJob(CamelModel):
    job_id: int
    system: str
    working_directory: str
    logs: TransferJobLogs


class DataTransferType(str, Enum):
    """Types of data transfer services"""

    s3 = "s3"
    wormhole = "wormhole"
    streamer = "streamer"


class DataTransferDirective(CamelModel):
    transfer_method: Literal[
        DataTransferType.s3,
        DataTransferType.wormhole,
        DataTransferType.streamer,
    ]


class WormholeDataTransferDirective(DataTransferDirective):
    wormhole_code: Optional[str] = None
    transfer_method: Literal[DataTransferType.wormhole,]


class S3DataTransferDirective(DataTransferDirective):
    download_url: Optional[str] = None
    parts_upload_urls: Optional[List[str]] = None
    complete_upload_url: Optional[str] = None
    max_part_size: Optional[int] = None
    file_size: Optional[int] = Field(
        None, description="Size of the file to upload in bytes"
    )
    transfer_method: Literal[DataTransferType.s3,]


class DataTransferLocation(CamelModel):
    host: Optional[str] = None
    system: Optional[str] = None
    path: Optional[str] = None
    transfer_directives: Optional[
        Union[S3DataTransferDirective | WormholeDataTransferDirective]
    ] = Field(
        None,
        description=("Provide method specific transfer directives"),
        discriminator="transfer_method",
    )

    model_config = ConfigDict(use_enum_values=True)


class DataTransferOperation(CamelModel):
    transfer_job: TransferJob
    transfer_directives: Union[
        S3DataTransferDirective | WormholeDataTransferDirective
    ] = Field(
        None,
        description=("Provide method specific transfer directives"),
        discriminator="transfer_method",
    )

    class Config:
        json_encoders = {
            DataTransferDirective: lambda d: {
                k: v for k, v in d.__dict__.items() if v is not None
            }
        }


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


def _format_directives(directives: List[str], account: str):

    directives_str = "\n".join(directives)
    if "{account}" in directives_str:
        if account is None:
            raise HTTPException(
                status_code=400, detail="Account parameter is required on this system."
            )
        directives_str = directives_str.format(account=account)

    return directives_str


def _build_script(filename: str, parameters):

    script_environment = Environment(
        loader=FileSystemLoader(imp_resources.files(scripts)), autoescape=True
    )
    script_template = script_environment.get_template(filename)

    script_code = script_template.render(parameters)

    return script_code


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
