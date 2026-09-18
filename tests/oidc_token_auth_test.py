# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from fastapi import HTTPException

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


AUD_A = "https://firecrest-a.example.com"
AUD_B = "https://firecrest-b.example.com"


def _rejected(audience, claims) -> bool:
    auth = OIDCTokenAuth(public_certs=[], audience=audience)
    try:
        auth._validate_audience(claims, "the-access-token")
    except HTTPException:
        return True
    return False


def test_audience_validation_is_skipped_when_unconfigured():
    # Deployments that do not set the audience option, must accept
    # all tokens, including ones with no aud record at all.
    assert not _rejected(None, {})
    assert not _rejected(None, {"aud": "anything-at-all"})


def test_missing_aud_claim_is_rejected():
    assert _rejected([AUD_A], {"sub": "user"})


def test_wrong_audience_is_rejected():
    assert _rejected([AUD_A], {"aud": AUD_B})


def test_any_configured_audience_is_accepted():
    assert not _rejected([AUD_A, AUD_B], {"aud": AUD_A})
    assert not _rejected([AUD_A, AUD_B], {"aud": AUD_B})
    assert _rejected([AUD_A, AUD_B], {"aud": "https://elsewhere.example.com"})


def test_token_carrying_several_audiences_needs_only_one_match():
    assert not _rejected([AUD_A], {"aud": ["https://other.example.com", AUD_A]})
    assert _rejected([AUD_A], {"aud": ["https://other.example.com"]})
