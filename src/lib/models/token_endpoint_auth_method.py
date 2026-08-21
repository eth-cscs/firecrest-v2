# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum


class TokenEndpointAuthMethod(str, Enum):
    client_secret_post = "client_secret_post"  # noqa: S105 - avoids hardcoded password string, this is a standard OAuth2 authentication method
    client_secret_basic = "client_secret_basic"  # noqa: S105 - avoids hardcoded password string, this is a standard OAuth2 authentication method
