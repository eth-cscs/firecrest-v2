# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.models.config_model import Oidc, DEFAULT_MIN_TOKEN_TTL


def test_oidc_min_token_ttl_defaults_to_shared_constant():
    """The Oidc config model should default min_token_ttl to the shared
    DEFAULT_MIN_TOKEN_TTL (currently 5 seconds), the same value used by
    OIDCTokenAuth when instantiated without an explicit min_token_ttl.
    """
    oidc = Oidc(token_url="https://example.com/token")

    assert oidc.min_token_ttl == DEFAULT_MIN_TOKEN_TTL == 5


def test_oidc_min_token_ttl_can_be_overridden():
    oidc = Oidc(token_url="https://example.com/token", min_token_ttl=60)

    assert oidc.min_token_ttl == 60
