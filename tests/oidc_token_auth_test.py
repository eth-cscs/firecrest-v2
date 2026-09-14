# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.auth.authN.OIDC_token_auth import OIDCTokenAuth
from lib.models.config_model import DEFAULT_MIN_TOKEN_TTL


def test_default_min_token_ttl_matches_shared_constant():
    """OIDCTokenAuth should fall back to the shared DEFAULT_MIN_TOKEN_TTL
    (currently 5 seconds) when no min_token_ttl is supplied, keeping it in
    sync with the Oidc config model default.
    """
    auth = OIDCTokenAuth(public_certs=[])

    assert auth.min_token_ttl == DEFAULT_MIN_TOKEN_TTL == 5


def test_explicit_min_token_ttl_overrides_default():
    auth = OIDCTokenAuth(public_certs=[], min_token_ttl=42)

    assert auth.min_token_ttl == 42
