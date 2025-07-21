import sys
from typing import Dict, List, Optional
from humps import camelize
from pydantic import BaseModel, ConfigDict

sys.path.append("../../../src")
sys.path.append("../")
from firecrest.config import Settings, HPCCluster, ServiceAccount, SSHClientPool, SSHStaticKeys, Storage


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
    public_cert: Optional[str] = None
    passphrase: Optional[str] = None


class UnsafeSSHUserKeys(SSHStaticKeys):
    keys: Dict[str, UnsafeSSHStaticKeys]
    type: str = "SSHStaticKeys"


class UnsafeServiceAccount(ServiceAccount):
    client_id: str
    secret: str


class UnsafeHPCCluster(HPCCluster):
    service_account: UnsafeServiceAccount
    ssh: UnsafeSSHClientPool


class UnsafeStorage(Storage):
    secret_access_key: str
    access_key_id: str
    private_url: str


class UnsafeSettings(Settings):
    ssh_credentials: UnsafeSSHUserKeys
    clusters: List[UnsafeHPCCluster] = []
    storage: UnsafeStorage
