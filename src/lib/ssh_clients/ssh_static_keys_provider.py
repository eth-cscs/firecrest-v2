# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import Dict
from lib.exceptions import SSHCredentials
from lib.models.config_model import SSHUserKeys
from lib.ssh_clients.ssh_credentials_provider import SSHCredentialsProvider


class SSHStaticKeysProvider(SSHCredentialsProvider):

    def __init__(self, users_keys: Dict[str, SSHUserKeys]):
        self.users_keys = users_keys

    async def get_credentials(self, username: str, jwt_token: str):

        if username in self.users_keys:
            return SSHCredentialsProvider.SSHCredentials(
                **{
                    "private_key": self.users_keys[
                        username
                    ].private_key.get_secret_value(),
                    "public_certificate": self.users_keys[username].public_cert,
                    "passphrase": (
                        self.users_keys[username].passphrase.get_secret_value()
                        if self.users_keys[username].passphrase
                        else None
                    ),
                }
            )
        else:
            raise SSHCredentials(f"No SSH credentials found for user:{username}")
