import sys
from typing import Dict, List, Optional
from humps import camelize
from pydantic import BaseModel, ConfigDict, Field

sys.path.append("../../../src")
sys.path.append("../")
from firecrest.config import (
    Settings,
    HPCCluster,
    ServiceAccount,
    SSHClientPool,
    SSHStaticKeys,
    DataOperation,
    BaseDataTransfer,
)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=camelize,
        arbitrary_types_allowed=True,
        populate_by_name=True,
        validate_assignment=True,
    )


class UnsafeSSHClientPool(SSHClientPool):
    pass


class UnsafeSSHStaticKeys(BaseModel):
    private_key: str
    public_cert: Optional[str] = Field(None, nullable=True)
    passphrase: Optional[str] = Field(None, nullable=True)


class UnsafeSSHUserKeys(SSHStaticKeys):
    keys: Dict[str, UnsafeSSHStaticKeys]
    type: str = "SSHStaticKeys"


class UnsafeServiceAccount(ServiceAccount):
    client_id: str
    secret: str


class UnsafeS3DataTransfer(BaseDataTransfer):
    service_type: str
    name: str
    secret_access_key: str
    access_key_id: str
    private_url: str
    public_url: str
    region: str
    ttl: int


class UnsafeDataOperation(DataOperation):
    data_transfer: UnsafeS3DataTransfer


class UnsafeHPCCluster(HPCCluster):
    service_account: UnsafeServiceAccount
    ssh: UnsafeSSHClientPool
    data_operation: UnsafeDataOperation


class UnsafeSettings(Settings):
    ssh_credentials: UnsafeSSHUserKeys
    clusters: List[UnsafeHPCCluster] = []
