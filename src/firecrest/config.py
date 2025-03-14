# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Tuple, Type
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from datetime import datetime
from functools import lru_cache
from typing import List, Optional

from lib.models.base_model import CamelModel
from lib.models.config_model import LoadFileSecretStr, Oidc, SSHUserKeys


class MultipartUpload(BaseModel):
    use_split: Optional[bool] = False
    max_part_size: Optional[int] = 2 * 1024 * 1024 * 1024
    parallel_runs: Optional[int] = 3
    tmp_folder: Optional[str] = "tmp"


class BucketLifestyleConfiguration(BaseModel):
    days: Optional[int] = 10

    def to_json(self):
        return {
            "Rules": [
                {
                    "ID": "ExpireObjects",
                    "Prefix": "",
                    "Status": "Enabled",
                    "Expiration": {"Days": self.days},
                }
            ]
        }


class StorageProbing(CamelModel):
    timeout: int


class Storage(BaseModel):
    name: str
    private_url: str
    public_url: str
    access_key_id: str
    secret_access_key: LoadFileSecretStr
    region: str
    ttl: int
    tenant: Optional[str] = None
    multipart: Optional[MultipartUpload] = MultipartUpload()
    bucket_lifecycle_configuration: Optional[BucketLifestyleConfiguration] = (
        BucketLifestyleConfiguration()
    )
    max_ops_file_size: Optional[int] = 5 * 1024 * 1024
    probing: Optional[StorageProbing] = None


class SchedulerType(str, Enum):
    slurm = "slurm"


class FileSystemDataType(str, Enum):
    users = "users"
    store = "store"
    archive = "archive"
    apps = "apps"
    scratch = "scratch"
    project = "project"


class Scheduler(CamelModel):
    type: SchedulerType
    version: Optional[str] = None
    api_url: Optional[str] = None
    api_version: Optional[str] = None
    timeout: Optional[int] = 10

    model_config = ConfigDict(use_enum_values=True)


class ServiceAccount(CamelModel):
    client_id: str
    secret: LoadFileSecretStr


class ClusterNodesHealth(CamelModel):
    available: int = 0
    total: int = 0


class HealthCheckType(str, Enum):
    scheduler = "scheduler"
    filesystem = "filesystem"
    ssh = "ssh"
    s3 = "s3"


class BaseServiceHealth(CamelModel):
    service_type: HealthCheckType
    last_checked: Optional[datetime] = None
    latency: Optional[float] = None
    healthy: Optional[bool] = False
    message: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class SchedulerServiceHealth(BaseServiceHealth):
    nodes: Optional[ClusterNodesHealth] = None


class FilesystemServiceHealth(BaseServiceHealth):
    path: Optional[str] = None


class SSHServiceHealth(BaseServiceHealth):
    pass


class S3ServiceHealth(BaseServiceHealth):
    pass


class ClusterProbing(CamelModel):
    interval: int
    timeout: int


class FileSystem(CamelModel):
    path: str
    data_type: FileSystemDataType
    default_work_dir: Optional[bool] = False

    model_config = ConfigDict(use_enum_values=True)


class SSHTimeouts(CamelModel):
    connection: Optional[int] = 5
    login: Optional[int] = 5
    command_execution: Optional[int] = 5
    idle_timeout: Optional[int] = 60
    keep_alive: Optional[int] = 5


class SSHClientPool(CamelModel):
    host: str
    port: int
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    max_clients: Optional[int] = 100
    timeout: Optional[SSHTimeouts] = SSHTimeouts()


class HPCCluster(CamelModel):
    name: str
    ssh: SSHClientPool
    scheduler: Scheduler
    service_account: ServiceAccount = Field(exclude=True)
    servicesHealth: Optional[
        List[
            SchedulerServiceHealth
            | FilesystemServiceHealth
            | SSHServiceHealth
            | S3ServiceHealth
        ]
    ] = None
    probing: Optional[ClusterProbing] = None
    file_systems: Optional[List[FileSystem]] = None
    datatransfer_jobs_directives: Optional[List[str]] = []


class OpenFGA(CamelModel):
    url: str
    timeout: Optional[int] = 1
    max_connections: Optional[int] = 100


class SSHKeysService(CamelModel):
    url: str
    max_connections: Optional[int] = 100


class Auth(CamelModel):
    authentication: Oidc = None
    authorization: Optional[OpenFGA] = None


class Settings(BaseSettings):
    # FastAPI App variables
    app_debug: bool = False
    app_version: str = "2.x.x"
    apis_root_path: str = ""
    doc_servers: Optional[List[Dict]] = None
    # Authentication and Authorization settings
    auth: Auth = None
    # SSH Credentials
    ssh_credentials: SSHKeysService | Dict[str, SSHUserKeys]
    # HPC Clusters definition
    clusters: List[HPCCluster] = []
    # HPC Storage definition
    storage: Optional[Storage] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @field_validator("clusters", mode="before")
    @classmethod
    def ensure_list(cls, value: Any) -> Any:
        if isinstance(value, str) and value.startswith("path:"):
            path = Path(value[5:]).expanduser()
            if not path.exists():
                raise FileNotFoundError(f"Clusters config path: {path} not found!")
            if not path.is_dir:
                raise FileNotFoundError(
                    f"Clusters config path: {path} is not a folder!"
                )
            clusters = []
            for dirpath, _dirs, files in os.walk(path):
                for file in files:
                    if file.endswith(".yaml"):
                        with open(os.path.join(dirpath, file)) as stream:
                            clusters.append(
                                HPCCluster.model_validate(yaml.safe_load(stream))
                            )
            return clusters
        else:
            return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        yaml_file = os.getenv("YAML_CONFIG_FILE", None)
        if yaml_file is None:
            yaml_file = os.getenv("INPUT_YAML_CONFIG_FILE", None)
        if yaml_file is None or yaml_file == "":
            raise EnvironmentError("Missing YAML_CONFIG_FILE environment variable")
        return (
            init_settings,
            YamlConfigSettingsSource(
                settings_cls=settings_cls,
                yaml_file=yaml_file,
                yaml_file_encoding="utf-8",
            ),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


@lru_cache()
def get_settings():
    return Settings()
