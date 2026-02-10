# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field


class SSHCredentialsProvider(ABC):

    class SSHCredentials(BaseModel):
        private_key: str
        public_certificate: Optional[str] = Field(default=None, nullable=True)
        passphrase: Optional[str] = Field(default=None, nullable=True)

    @abstractmethod
    async def get_credentials(self, username: str, jwt_token: str) -> SSHCredentials:
        pass
