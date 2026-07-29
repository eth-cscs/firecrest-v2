# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status

from starlette_context import request_cycle_context
from starlette_context.header_keys import HeaderKeys

from lib.ssh_clients.ssh_keygen_credentials_provider import (
    SSHKeygenCredentialsProvider,
    _ssh_service_headers,
)
from lib.exceptions import SSHServiceError

SSH_KEYGEN_URL = "http://fake-ssh-service"
APP_VERSION = "2.x.x"
FAKE_SSH_RESPONSE = {
    "sshKey": {
        "privateKey": "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----",
        "publicKey": "ssh-rsa AAAAB3NzaC1yc2E fake",
    }
}


# ---------------------------------------------------------------------------
# _ssh_service_headers — unit tests
# ---------------------------------------------------------------------------


def test_headers_default_fields():
    headers = _ssh_service_headers("token-abc", APP_VERSION)

    assert headers["Authorization"] == "Bearer token-abc"
    assert headers["x-client-type"] == "api"
    assert headers["x-client-name"] == "firecrest"
    assert headers["x-client-version"] == APP_VERSION
    assert "x-request-id" not in headers
    assert "x-trace-id" not in headers


def test_headers_include_request_and_trace_id_when_present():
    with request_cycle_context(
        {HeaderKeys.request_id: "req-123", HeaderKeys.correlation_id: "corr-456"}
    ):
        headers = _ssh_service_headers("token-abc", APP_VERSION)

    assert headers["x-request-id"] == "req-123"
    assert headers["x-trace-id"] == "corr-456"


def test_headers_omit_request_and_trace_id_when_absent_from_context():
    with request_cycle_context({}):
        headers = _ssh_service_headers("token-abc", APP_VERSION)

    assert "x-request-id" not in headers
    assert "x-trace-id" not in headers


def test_headers_safe_outside_request_response_cycle():
    # No starlette_context set up at all, e.g. when called from a background
    # scheduler task (health checks) rather than an HTTP request.
    headers = _ssh_service_headers("token-abc", APP_VERSION)

    assert "x-request-id" not in headers
    assert "x-trace-id" not in headers


# ---------------------------------------------------------------------------
# SSHKeygenCredentialsProvider.get_credentials — integration tests
# ---------------------------------------------------------------------------


def _make_mock_session(
    response_status: int, response_payload: dict = None, response_body: str = ""
):
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
    provider = SSHKeygenCredentialsProvider(SSH_KEYGEN_URL, app_version=APP_VERSION)
    mock_session = _make_mock_session(status.HTTP_201_CREATED, FAKE_SSH_RESPONSE)

    with patch.object(
        SSHKeygenCredentialsProvider,
        "get_aiohttp_client",
        AsyncMock(return_value=mock_session),
    ):
        credentials = await provider.get_credentials("fireuser", "token-abc")

    assert credentials.private_key.startswith("-----BEGIN OPENSSH PRIVATE KEY-----")
    assert credentials.public_certificate.startswith("ssh-rsa")


async def test_get_credentials_sends_default_monitoring_headers():
    provider = SSHKeygenCredentialsProvider(SSH_KEYGEN_URL, app_version=APP_VERSION)
    mock_session = _make_mock_session(status.HTTP_201_CREATED, FAKE_SSH_RESPONSE)

    with patch.object(
        SSHKeygenCredentialsProvider,
        "get_aiohttp_client",
        AsyncMock(return_value=mock_session),
    ):
        await provider.get_credentials("fireuser", "token-abc")

    sent = _sent_headers(mock_session)
    assert sent["x-client-type"] == "api"
    assert sent["x-client-name"] == "firecrest"
    assert sent["x-client-version"] == APP_VERSION
    assert "x-request-id" not in sent
    assert "x-trace-id" not in sent


async def test_get_credentials_forwards_request_and_trace_id():
    provider = SSHKeygenCredentialsProvider(SSH_KEYGEN_URL, app_version=APP_VERSION)
    mock_session = _make_mock_session(status.HTTP_201_CREATED, FAKE_SSH_RESPONSE)

    with patch.object(
        SSHKeygenCredentialsProvider,
        "get_aiohttp_client",
        AsyncMock(return_value=mock_session),
    ):
        with request_cycle_context(
            {HeaderKeys.request_id: "req-456", HeaderKeys.correlation_id: "corr-789"}
        ):
            await provider.get_credentials("fireuser", "token-abc")

    sent = _sent_headers(mock_session)
    assert sent["x-request-id"] == "req-456"
    assert sent["x-trace-id"] == "corr-789"


async def test_get_credentials_raises_on_non_201():
    provider = SSHKeygenCredentialsProvider(SSH_KEYGEN_URL, app_version=APP_VERSION)
    mock_session = _make_mock_session(
        status.HTTP_500_INTERNAL_SERVER_ERROR, response_body="Internal error"
    )

    with patch.object(
        SSHKeygenCredentialsProvider,
        "get_aiohttp_client",
        AsyncMock(return_value=mock_session),
    ):
        with pytest.raises(SSHServiceError):
            await provider.get_credentials("fireuser", "token-abc")
