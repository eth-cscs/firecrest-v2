# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum
import os
import pydantic
import yaml
from pathlib import Path
from typing import Any, Dict, Literal, Tuple, Type, Union
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
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
from lib.datatransfers.datatransfer_base import DataTransferType


class MultipartUpload(BaseModel):
    """Configuration for multipart upload behavior."""

    use_split: bool = Field(
        False,
        description=(
            "Enable or disable splitting large files into parts when "
            "uploading the file to the staging area."
        ),
    )
    max_part_size: int = Field(
        2 * 1024 * 1024 * 1024,
        description=(
            "Maximum size (in bytes) for multipart data transfers. Default is 2 GB."
        ),
    )
    parallel_runs: int = Field(
        3, description="Number of parts to upload in parallel to the staging area."
    )
    tmp_folder: str = Field(
        "tmp",
        description="Temporary folder used for storing split parts during upload.",
    )


class BucketLifecycleConfiguration(BaseModel):
    """Configuration for automatic object lifecycle in storage buckets."""

    days: int = Field(
        10,
        description="Number of days after which objects will expire automatically.",
    )

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


class SchedulerType(str, Enum):
    """Supported job scheduler types."""

    slurm = "slurm"
    pbs = "pbs"


class FileSystemDataType(str, Enum):
    """Data types for cluster file systems."""

    users = "users"
    store = "store"
    archive = "archive"
    apps = "apps"
    scratch = "scratch"
    project = "project"


class Scheduler(CamelModel):
    """Cluster job scheduler configuration."""

    type: SchedulerType = Field(..., description="Scheduler type.")
    version: str = Field(..., description="Scheduler version.")
    api_url: Optional[str] = Field(None, description="REST API endpoint for scheduler.")
    api_version: Optional[str] = Field(None, description="Scheduler API version.")
    timeout: Optional[int] = Field(
        10, description="Timeout in seconds for scheduler communication with the API."
    )

    model_config = ConfigDict(use_enum_values=True)


class ServiceAccount(CamelModel):
    """Internal service account credentials."""

    client_id: str = Field(..., description="Service account client ID.")
    secret: LoadFileSecretStr = Field(
        ...,
        description=(
            "Service account secret token. You can give directly the "
            "content or the file path using `'secret_file:/path/to/file'`."
        ),
    )


class HealthCheckType(str, Enum):
    """Types of services that can be health-checked."""

    scheduler = "scheduler"
    filesystem = "filesystem"
    ssh = "ssh"
    s3 = "s3"
    exception = "exception"


class BaseServiceHealth(CamelModel):
    """Base health status structure for services."""

    service_type: HealthCheckType = Field(
        ..., description="Type of the service being checked."
    )
    last_checked: Optional[datetime] = Field(
        None, description="Timestamp of the last health check."
    )
    latency: Optional[float] = Field(
        None, description="Service response latency in seconds."
    )
    healthy: Optional[bool] = Field(
        False, description="True if the service is healthy."
    )
    message: Optional[str] = Field(None, description="Optional status message.")

    model_config = ConfigDict(use_enum_values=True)


class SchedulerServiceHealth(BaseServiceHealth):
    """Health check result for the job scheduler."""

    pass


class FilesystemServiceHealth(BaseServiceHealth):
    """Health check for a mounted file system."""

    path: Optional[str] = Field(None, description="Path of the monitored file system.")


class SSHServiceHealth(BaseServiceHealth):
    """Health status of SSH service."""

    pass


class S3ServiceHealth(BaseServiceHealth):
    """Health status of S3-compatible storage."""

    pass


class HealthCheckException(BaseServiceHealth):
    """Generic health check error placeholder."""

    pass


class Probing(CamelModel):
    """Cluster monitoring attributes."""

    interval: int = Field(
        ..., description="Interval in seconds between cluster checks."
    )
    timeout: int = Field(..., description="Maximum time in seconds allowed per check.")


class BaseDataTransfer(CamelModel):
    """Base data transfer setting"""

    service_type: Literal[
        DataTransferType.s3,
        DataTransferType.wormhole,
    ] = Field(None, description="Type of data transfer service.")

    probing: Optional[Probing] = Field(
        None, description="Configuration for probing storage availability."
    )
    servicesHealth: Optional[List[S3ServiceHealth | HealthCheckException]] = Field(
        None,
        description="Optional health information for different services in the cluster.",
    )

    model_config = ConfigDict(use_enum_values=True)


class S3DataTransfer(BaseDataTransfer):
    """Object storage configuration, including credentials, endpoints, and upload behavior."""

    service_type: Literal[DataTransferType.s3]
    name: str = Field(..., description="Name identifier for the storage.")
    private_url: SecretStr = Field(
        ..., description="Private/internal endpoint URL for the storage."
    )
    public_url: str = Field(..., description="Public/external URL for the storage.")
    access_key_id: SecretStr = Field(
        ..., description="Access key ID for S3-compatible storage."
    )
    secret_access_key: LoadFileSecretStr = Field(
        ...,
        description=(
            "Secret access key for storage. You can give directly the "
            "content or the file path using `'secret_file:/path/to/file'`."
        ),
    )
    region: str = Field(..., description="Region of the storage bucket.")
    ttl: int = Field(..., description="Time-to-live (in seconds) for generated URLs.")
    tenant: Optional[str] = Field(
        None, description="Optional tenant identifier for multi-tenant setups."
    )
    multipart: MultipartUpload = Field(
        default_factory=MultipartUpload,
        description="Settings for multipart upload, including chunk size and concurrency.",
    )
    bucket_lifecycle_configuration: BucketLifecycleConfiguration = Field(
        default_factory=BucketLifecycleConfiguration,
        description="Lifecycle policy settings for auto-deleting files after a given number of days.",
    )


class WormholeTransfer(BaseDataTransfer):
    service_type: Literal[DataTransferType.wormhole]
    pass


class DataOperation(BaseModel):
    max_ops_file_size: int = Field(
        5 * 1024 * 1024,
        description=(
            "Maximum file size (in bytes) allowed for direct upload and "
            "download. Larger files will go through the staging area."
        ),
    )
    data_transfer: Optional[S3DataTransfer | WormholeTransfer] = Field(
        None,
        description=("Data transfer service configuration"),
        discriminator="service_type",
    )


class FileSystem(CamelModel):
    """Defines a cluster file system and its type."""

    path: str = Field(..., description="Mount path for the file system.")
    data_type: FileSystemDataType = Field(..., description="File system purpose/type.")
    default_work_dir: bool = Field(
        False, description="Mark this as the default working directory."
    )

    model_config = ConfigDict(use_enum_values=True)


class SSHTimeouts(CamelModel):
    """Various SSH settings."""

    connection: int = Field(
        5, description="Timeout (seconds) for initial SSH connection."
    )
    login: int = Field(5, description="Timeout (seconds) for SSH login/auth.")
    command_execution: int = Field(
        5, description="Timeout (seconds) for executing commands over SSH."
    )
    idle_timeout: int = Field(
        60, description="Max idle time (seconds) before disconnecting."
    )
    keep_alive: int = Field(
        5, description="Interval (seconds) for sending keep-alive messages."
    )


class SSHClientPool(CamelModel):
    """SSH connection pool configuration for remote execution."""

    host: str = Field(..., description="SSH target hostname.")
    port: int = Field(..., description="SSH port.")
    proxy_host: Optional[str] = Field(
        None, description="Optional proxy host for tunneling."
    )
    proxy_port: Optional[int] = Field(None, description="Optional proxy port.")
    max_clients: int = Field(
        100, description="Maximum number of concurrent SSH clients."
    )
    timeout: SSHTimeouts = Field(
        default_factory=SSHTimeouts, description="SSH timeout settings."
    )


class HPCCluster(CamelModel):
    """
    Definition of an HPC cluster, including SSH access, scheduling, and
    filesystem layout. More info in
    [the systems' section](../arch/systems//README.md).
    """

    name: str = Field(
        ..., description="Unique name for the cluster. This field is case insensitive."
    )
    ssh: SSHClientPool = Field(
        ..., description="SSH configuration for accessing the cluster nodes."
    )
    scheduler: Scheduler = Field(..., description="Job scheduler configuration.")
    service_account: ServiceAccount = Field(
        ..., description="Service credentials for internal APIs.", exclude=True
    )
    servicesHealth: Optional[
        List[
            SchedulerServiceHealth
            | FilesystemServiceHealth
            | SSHServiceHealth
            | HealthCheckException
        ]
    ] = Field(
        None,
        description="Optional health information for different services in the cluster.",
    )
    probing: Probing = Field(
        ..., description="Probing configuration for monitoring the cluster."
    )
    file_systems: List[FileSystem] = Field(
        default_factory=list,
        description="List of mounted file systems on the cluster, such as scratch or home directories.",
    )
    datatransfer_jobs_directives: List[str] = Field(
        default_factory=list,
        description="Custom scheduler flags passed to data transfer jobs (e.g. `-pxfer` for a dedicated partition).",
    )

    @pydantic.field_validator("name", mode="before")
    def to_lowercase(cls, value):
        if isinstance(value, str):
            return value.lower()
        return value


class OpenFGA(CamelModel):
    """Authorization settings using OpenFGA."""

    url: str = Field(..., description="OpenFGA API base URL.")
    timeout: Optional[int] = Field(
        1,
        description="Connection timeout in seconds. When `None` the timeout is disabled.",
    )
    max_connections: int = Field(
        100,
        description="Max HTTP connections per host. When set to `0`, there is no limit.",
    )


class SSHKeysServiceType(str, Enum):
    """Supported job scheduler types."""

    SSHService = "SSHService"
    SSHCA = "SSHCA"
    SSHStaticKeys = "SSHStaticKeys"


class BaseSSHKeysService(CamelModel):

    type: Literal[
        SSHKeysServiceType.SSHService,
        SSHKeysServiceType.SSHCA,
        SSHKeysServiceType.SSHStaticKeys,
    ]


class SSHService(BaseSSHKeysService):
    """External service for managing SSH keys."""

    url: str = Field(..., description="URL of the SSH keys management service.")
    max_connections: int = Field(
        100,
        description=(
            "Maximum concurrent connections to the service. When set to "
            "`0`, there is no limit."
        ),
    )
    type: Literal[SSHKeysServiceType.SSHService]


class SSHCA(BaseSSHKeysService):
    """External service for managing SSH keys."""

    url: str = Field(..., description="URL of the SSH keys management service.")
    max_connections: int = Field(
        100,
        description=(
            "Maximum concurrent connections to the service. When set to "
            "`0`, there is no limit."
        ),
    )
    type: Literal[SSHKeysServiceType.SSHCA]


class SSHStaticKeys(BaseSSHKeysService):
    """External service for managing SSH keys."""

    keys: Dict[str, SSHUserKeys]
    type: Literal[SSHKeysServiceType.SSHStaticKeys]


class Auth(CamelModel):
    """Authentication and authorization configuration."""

    authentication: Oidc = Field(
        ...,
        description=(
            "OIDC authentication settings. More info in the "
            "[authentication section](../arch/auth/README.md#authentication)."
        ),
    )
    authorization: Optional[OpenFGA] = Field(
        None,
        description=(
            "Authorization settings via OpenFGA. More info in [the "
            "authorization section](../arch/auth/README.md#authorization)."
        ),
    )


class Logger(CamelModel):
    enable_tracing_log: bool = Field(
        False,
        description="Enable tracing logs.",
    )


class Settings(BaseSettings):
    """FirecREST configuration. Loaded from a YAML file."""

    app_debug: bool = Field(
        False, description="Enable debug mode for the FastAPI application."
    )
    app_version: Literal["2.x.x"] = "2.x.x"
    apis_root_path: str = Field(
        "",
        description="Base path prefix for exposing the APIs.",
    )
    doc_servers: Optional[List[dict]] = Field(
        None,
        description=(
            "Optional documentation servers. For complete"
            "documentation see the `servers` parameter in the"
            "[FastAPI docs](https://fastapi.tiangolo.com/reference/fastapi/#fastapi.FastAPI--example)."
        ),
    )
    auth: Auth = Field(
        ..., description="Authentication and authorization config (OIDC, FGA)."
    )

    ssh_credentials: Union[SSHService, SSHCA, SSHStaticKeys] = Field(
        ...,
        description=(
            "SSH keys service or manually defined user keys. More details in "
            "[this section](../arch/systems/README.md#obtaining-ssh-credentials-on-behalf-of-the-user)."
        ),
        discriminator="type",
    )
    clusters: List[HPCCluster] = Field(
        default_factory=list, description="List of configured HPC clusters."
    )
    data_operation: Optional[DataOperation] = Field(
        DataOperation(),
        description=(
            "Data transfer backend configuration. More details in "
            "[this section](../arch/external_storage/README.md)."
        ),
    )
    logger: Logger = Field(
        default_factory=Logger, description="Logging configuration options."
    )

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
            for file in Path(path).glob("*.yaml"):
                with open(file) as stream:
                    clusters.append(HPCCluster.model_validate(yaml.safe_load(stream)))
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
