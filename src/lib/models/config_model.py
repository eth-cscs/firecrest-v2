from pathlib import Path
from typing import List, Optional

from pydantic import SecretStr
from lib.models.base_model import CamelModel


class Oidc(CamelModel):
    scopes: Optional[dict] = {}
    token_url: str
    public_certs: List[str] = []


class LoadFileSecretStr(SecretStr):

    def __init__(self, secret_value: str) -> None:
        if secret_value.startswith("secret_file:"):
            secrets_path = Path(secret_value[12:]).expanduser()
            if not secrets_path.exists() or not secrets_path.is_file:
                raise FileNotFoundError(f"Secret file: {secrets_path} not found!")
            secret_value = secrets_path.read_text("utf-8").strip()
        super().__init__(secret_value)


class SSHUserKeys(CamelModel):
    private_key: LoadFileSecretStr
    public_key: str
