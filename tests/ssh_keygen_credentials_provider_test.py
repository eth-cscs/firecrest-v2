# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status

from lib.request_vars import request_global
from lib.ssh_clients.ssh_keygen_credentials_provider import (
    SSHKeygenCredentialsProvider,
    _ssh_service_headers,
)
from lib.exceptions import SSHServiceError


SSH_KEYGEN_URL = "http://fake-ssh-service"

FAKE_SSH_RESPONSE = {
    "sshKey": {
        "privateKey": "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----",
        "publicKey": "ssh-rsa AAAAB3NzaC1yc2E fake",
    }
}


def _set_context(**kwargs):
    request_global.set(types.SimpleNamespace(**kwargs))


def _clear_context():
    request_global.set(types.SimpleNamespace())


# ---------------------------------------------------------------------------
# _ssh_service_headers — unit tests
# ---------------------------------------------------------------------------


def test_headers_default_when_no_client_headers():
    _clear_context()
    headers = _ssh_service_headers("token-abc")

    assert headers["Authorization"] == "Bearer token-abc"
    assert headers["x-client-type"] == "api"
    assert headers["x-client-name"] == "firecrest"
    assert "x-client-version" not in headers
    assert "x-request-id" not in headers


def test_headers_forwarded_when_client_sends_all():
    _set_context(
        x_request_id="req-123",
        x_client_type="sdk",
        x_client_name="my-client",
        x_client_version="1.2.3",
    )
    headers = _ssh_service_headers("token-abc")

    assert headers["x-request-id"] == "req-123"
    assert headers["x-client-type"] == "sdk"
    assert headers["x-client-name"] == "my-client"
    assert headers["x-client-version"] == "1.2.3"


def test_headers_partial_forward_falls_back_to_defaults():
    _set_context(
        x_client_type="sdk",
        # x_client_name and x_client_version not set by client
    )
    headers = _ssh_service_headers("token-abc")

    assert headers["x-client-type"] == "sdk"
    assert headers["x-client-name"] == "firecrest"
    assert "x-client-version" not in headers
    assert "x-request-id" not in headers


def test_x_request_id_omitted_when_absent():
    _set_context(x_client_type="api")
    headers = _ssh_service_headers("token-abc")

    assert "x-request-id" not in headers


def test_x_request_id_omitted_when_none():
    _set_context(x_request_id=None)
    headers = _ssh_service_headers("token-abc")

    assert "x-request-id" not in headers


def test_empty_string_client_headers_fall_back_to_defaults():
    _set_context(x_client_type="", x_client_name="", x_client_version="")
    headers = _ssh_service_headers("token-abc")

    assert headers["x-client-type"] == "api"
    assert headers["x-client-name"] == "firecrest"
    assert "x-client-version" not in headers


# ---------------------------------------------------------------------------
# SSHKeygenCredentialsProvider.get_credentials — integration tests
# ---------------------------------------------------------------------------


def _make_mock_session(response_status: int, response_payload: dict = None, response_body: str = ""):
    mock_response = MagicMock()
    mock_response.status = response_status
    mock_response.json = AsyncMock(return_value=response_payload)
    mock_response.text = AsyncMock(return_value=response_body)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_context)
    return mock_session


def _sent_headers(mock_session) -> dict:
    return mock_session.post.call_args.kwargs["headers"]


async def test_get_credentials_returns_ssh_keys():
    _clear_context()
    provider = SSHKeygenCredentialsProvider(SSH_KEYGEN_URL)
    mock_session = _make_mock_session(status.HTTP_201_CREATED, FAKE_SSH_RESPONSE)

    with patch.object(SSHKeygenCredentialsProvider, "get_aiohttp_client", AsyncMock(return_value=mock_session)):
        credentials = await provider.get_credentials("fireuser", "token-abc")

    assert credentials.private_key.startswith("-----BEGIN OPENSSH PRIVATE KEY-----")
    assert credentials.public_certificate.startswith("ssh-rsa")


async def test_get_credentials_sends_default_monitoring_headers():
    _clear_context()
    provider = SSHKeygenCredentialsProvider(SSH_KEYGEN_URL)
    mock_session = _make_mock_session(status.HTTP_201_CREATED, FAKE_SSH_RESPONSE)

    with patch.object(SSHKeygenCredentialsProvider, "get_aiohttp_client", AsyncMock(return_value=mock_session)):
        await provider.get_credentials("fireuser", "token-abc")

    sent = _sent_headers(mock_session)
    assert sent["x-client-type"] == "api"
    assert sent["x-client-name"] == "firecrest"
    assert "x-client-version" not in sent
    assert "x-request-id" not in sent


async def test_get_credentials_forwards_client_headers():
    _set_context(
        x_request_id="req-456",
        x_client_type="sdk",
        x_client_name="my-app",
        x_client_version="3.0.0",
    )
    provider = SSHKeygenCredentialsProvider(SSH_KEYGEN_URL)
    mock_session = _make_mock_session(status.HTTP_201_CREATED, FAKE_SSH_RESPONSE)

    with patch.object(SSHKeygenCredentialsProvider, "get_aiohttp_client", AsyncMock(return_value=mock_session)):
        await provider.get_credentials("fireuser", "token-abc")

    sent = _sent_headers(mock_session)
    assert sent["x-request-id"] == "req-456"
    assert sent["x-client-type"] == "sdk"
    assert sent["x-client-name"] == "my-app"
    assert sent["x-client-version"] == "3.0.0"


async def test_get_credentials_raises_on_non_201():
    _clear_context()
    provider = SSHKeygenCredentialsProvider(SSH_KEYGEN_URL)
    mock_session = _make_mock_session(status.HTTP_500_INTERNAL_SERVER_ERROR, response_body="Internal error")

    with patch.object(SSHKeygenCredentialsProvider, "get_aiohttp_client", AsyncMock(return_value=mock_session)):
        with pytest.raises(SSHServiceError):
            await provider.get_credentials("fireuser", "token-abc")
