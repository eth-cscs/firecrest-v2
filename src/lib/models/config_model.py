# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from pathlib import Path
from typing import List, Optional

from pydantic import SecretStr, Field
from lib.models.base_model import CamelModel


class Oidc(CamelModel):
    """
    OpenID Connect (OIDC) authentication configuration.
    """

    scopes: Optional[dict] = Field(
        default_factory=dict, description="Map of OIDC scopes and their purposes."
    )
    token_url: str = Field(
        ...,
        description=(
            "Token endpoint URL for the OIDC provider. This is used to "
            "obtain access tokens for the service account that will do the "
            "health checks."
        ),
    )
    public_certs: List[str] = Field(
        default_factory=list,
        description=(
            "List of URLs for retrieving public certificates. These are used "
            "to verify the OIDC token."
        ),
    )


class LoadFileSecretStr(SecretStr):
    """
    Extended SecretStr that supports loading secrets from a file using the 'secret_file:' prefix.

    Example:
        LoadFileSecretStr("secret_file:/path/to/secret.txt") will read the secret from the file.
    """

    def __init__(self, secret_value: str) -> None:
        if secret_value.startswith("secret_file:"):
            secrets_path = Path(secret_value[12:]).expanduser()
            if not secrets_path.exists() or not secrets_path.is_file():
                raise FileNotFoundError(f"Secret file: {secrets_path} not found!")
            secret_value = secrets_path.read_text("utf-8").strip()
        super().__init__(secret_value)


class SSHUserKeys(CamelModel):
    """
    SSH key pair configuration for authenticating to remote systems.
    """

    private_key: LoadFileSecretStr = Field(
        ...,
        description=(
            "SSH private key. You can give directly the content or the file "
            "path using `'secret_file:/path/to/file'`."
        ),
    )
    public_cert: Optional[str] = Field(
        None, description="Optional SSH public certificate."
    )
    passphrase: Optional[LoadFileSecretStr] = Field(
        None,
        description=(
            "Optional passphrase for the private key. You can give "
            "directly the content or the file path using `'secret_file:/path/to/file'`."
        ),
    )
