# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum


class TokenEndpointAuthMethod(str, Enum):
    client_secret_post = "client_secret_post"
    client_secret_basic = "client_secret_basic"
