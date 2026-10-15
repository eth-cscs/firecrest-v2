# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from importlib import resources as impresources
import json
import ast
import logging
import pytest
from unittest.mock import AsyncMock, patch
from aioresponses import aioresponses
from pytest_httpx import HTTPXMock

from firecrest.plugins import settings
from firecrest.status.health_check.health_checker_cluster import ClusterHealthChecker
from firecrest.status.health_check.checks.health_check_ssh import SSHHealthCheck
from firecrest.status.health_check.checks.health_check_s3 import S3HealthCheck
from firecrest.status.health_check.checks.health_check_scheduler import SchedulerHealthCheck
from firecrest.status.health_check.checks.health_check_filesystem import FilesystemHealthCheck
from lib.auth.authN.OIDC_token_auth import OIDCTokenAuth
from lib.models.apis.api_auth_model import ApiAuthModel
from tests.mock_ssh_client import MockedCommand
from tests import mocked_api_responses
from firecrest.config import BackendServiceType


# import helpers functions to avoid duplicating code in tests
from tests.helpers import (
    mocked_ssh_ls_output,
    helper_test_userinfo,
    helper_test_get_job,
    helper_test_ls_command,
    load_ssh_output,
)


@pytest.fixture(scope="module")
def mocked_nodes_get_response():
    response_file = impresources.files(mocked_api_responses) / "slurm_get_nodes.json"
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_ssh_ls_wrong_path_output():
    return load_ssh_output("ssh_ls_command_wrong_path.json")


def mocked_token_response():
    return {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlcm5hbWUiOiJ0ZXN0IiwicHJlZmZlcmVkLXVzZXJuYW1lIjoidGVzdCJ9.9lEMnYRwLVeOTQKoXxzMd81zJNOAEnrDI3QtcJsUi7A",
        "expires_in": 300,
        "refresh_expires_in": 0,
        "token_type": "Bearer",
        "not-before-policy": 0,
        "scope": "profile email",
    }


class TokenDecoderMock(OIDCTokenAuth):

    def __init__(self):
        pass

    def auth_from_token(self, access_token: str):
        decoded_token = {
            "clientId": "firecrest-api",
            "preferred_username": "service-account-firecrest-api",
            "username": "service-account-firecrest-api",
        }
        return ApiAuthModel.build_from_oidc_decoded_token(decoded_token=decoded_token)


async def test_health_check(
    mocked_nodes_get_response,
    slurm_cluster_with_api_config,
    httpx_mock: HTTPXMock,
):
    # mock oidc response used to fetch the service accoount token
    httpx_mock.add_response(
        url=settings.auth.authentication.token_url, json=mocked_token_response()
    )

    with aioresponses() as mocked:

        mocked.get(
            "{root_url}/slurm/v0.0.38/nodes".format(
                root_url=slurm_cluster_with_api_config.scheduler.api_url
            ),
            status=200,
            body=json.dumps(mocked_nodes_get_response),
        )

        health_checker = ClusterHealthChecker(
            slurm_cluster_with_api_config, token_decoder=TokenDecoderMock()
        )
        await health_checker.check()

        assert slurm_cluster_with_api_config.servicesHealth is not None
        assert isinstance(slurm_cluster_with_api_config.servicesHealth, list)
        assert len(slurm_cluster_with_api_config.servicesHealth) > 0


async def test_health_check_disabled(
    slurm_cluster_with_ssh_no_health_check_config,
):

    # storage probing is configured
    assert BackendServiceType.external_storage in slurm_cluster_with_ssh_no_health_check_config.probing.services

    # ssh, scheduler and filesystem probing are not configured
    assert BackendServiceType.ssh not in slurm_cluster_with_ssh_no_health_check_config.probing.services
    assert BackendServiceType.scheduler not in slurm_cluster_with_ssh_no_health_check_config.probing.services
    assert BackendServiceType.filesystem not in slurm_cluster_with_ssh_no_health_check_config.probing.services


async def test_health_check_disabled_ok_with_ssh(
    client,
    ssh_client,
    slurm_cluster_with_ssh_no_health_check_config,
):

    await helper_test_userinfo(
        client,
        ssh_client,
        slurm_cluster_with_ssh_no_health_check_config.name
    )


async def test_health_check_disabled_ok_with_scheduler(
    client, ssh_client,
    slurm_cluster_with_ssh_no_health_check_config,
):
    await helper_test_get_job(
        client,
        ssh_client,
        slurm_cluster_with_ssh_no_health_check_config.name
    )


async def test_health_check_disabled_notok_with_filesystem(
        client, ssh_client, mocked_ssh_ls_wrong_path_output,
        slurm_cluster_with_ssh_no_health_check_config,):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_ls_wrong_path_output)]):

        response = client.get(
            "/filesystem/{cluster_name}/ops/ls?path={path}".format(
                cluster_name=slurm_cluster_with_ssh_no_health_check_config.name, path="/scratch"
            )
        )

        assert response.status_code == 404
        assert response.json() is not None


async def test_health_check_disabled_ok_with_no_filesystem(
        client, ssh_client,
        slurm_cluster_with_ssh_no_health_check_config,):

    await helper_test_ls_command(client, ssh_client,
                                 slurm_cluster_with_ssh_no_health_check_config.name)


async def test_health_check_disabled_not_ok_traversal(
    client, slurm_cluster_with_ssh_no_health_check_config
):
    response = client.get(
        f"/filesystem/{slurm_cluster_with_ssh_no_health_check_config.name}"
        "/ops/ls?path=/home/../etc/passwd"
    )
    assert response.status_code == 400


async def test_health_check_enabled_on_wrong_path(
    client, slurm_cluster_with_ssh_config
):
    response = client.get(
        f"/filesystem/{slurm_cluster_with_ssh_config.name}"
        "/ops/ls?path=/scratch"
    )
    assert response.status_code == 503


async def test_health_check_relative_path(
    client, slurm_cluster_with_ssh_config
):
    response = client.get(
        f"/filesystem/{slurm_cluster_with_ssh_config.name}"
        "/ops/ls?path=./home/fireuser"
    )
    assert response.status_code == 400


async def test_health_check_path_prefix_not_a_filesystem(
    client, slurm_cluster_with_ssh_config
):
    response = client.get(
        f"/filesystem/{slurm_cluster_with_ssh_config.name}/ops/ls?path=/home_private/x"
    )
    assert response.status_code == 400


async def test_health_check_ssh_failure_logs_error(
    slurm_cluster_with_ssh_config,
    caplog,
):
    auth = TokenDecoderMock().auth_from_token("")
    token = mocked_token_response()

    ssh_check = SSHHealthCheck(
        auth=auth,
        token=token,
        system=slurm_cluster_with_ssh_config,
        timeout=10,
    )

    with patch.object(
        SSHHealthCheck,
        "execute_check",
        new_callable=AsyncMock,
        side_effect=ConnectionError("SSH connection refused"),
    ):
        with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
            health = await ssh_check.check()

    record = caplog.records[0]
    payload = ast.literal_eval(record.getMessage())

    assert health.healthy is False
    assert payload["message"] == "Health check failed"
    assert payload["error.service"] == BackendServiceType.ssh.value
    assert payload["firecrest.username"] == auth.username
    assert payload["error.system"] == slurm_cluster_with_ssh_config.name
    assert "error.path" not in payload  # SSH health check does not have a filesystem path


async def test_health_check_scheduler_failure_logs_error(
    slurm_cluster_with_ssh_config,
    caplog,
):
    auth = TokenDecoderMock().auth_from_token("")
    token = mocked_token_response()

    scheduler_check = SchedulerHealthCheck(
        auth=auth,
        token=token,
        system=slurm_cluster_with_ssh_config,
        timeout=10,
    )

    with patch.object(
        SchedulerHealthCheck,
        "execute_check",
        new_callable=AsyncMock,
        side_effect=ConnectionError("SSH connection refused"),
    ):
        with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
            health = await scheduler_check.check()

    record = caplog.records[0]
    payload = ast.literal_eval(record.getMessage())

    assert health.healthy is False
    assert payload["message"] == "Health check failed"
    assert payload["error.service"] == BackendServiceType.scheduler.value
    assert payload["firecrest.username"] == auth.username
    assert payload["error.system"] == slurm_cluster_with_ssh_config.name
    assert "error.path" not in payload  # Scheduler health check does not have a filesystem path


async def test_health_check_filesystem_failure_logs_error(
    slurm_cluster_with_ssh_config,
    caplog,
):
    auth = TokenDecoderMock().auth_from_token("")
    token = mocked_token_response()

    filesystem_check = FilesystemHealthCheck(
        auth=auth,
        token=token,
        system=slurm_cluster_with_ssh_config,
        timeout=10,
        path=slurm_cluster_with_ssh_config.file_systems[0].path
    )

    with patch.object(
        FilesystemHealthCheck,
        "execute_check",
        new_callable=AsyncMock,
        side_effect=ConnectionError("SSH connection refused"),
    ):
        with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
            health = await filesystem_check.check()

    record = caplog.records[0]
    payload = ast.literal_eval(record.getMessage())

    assert health.healthy is False
    assert payload["message"] == "Health check failed"
    assert payload["error.service"] == BackendServiceType.filesystem.value
    assert payload["error.system"] == slurm_cluster_with_ssh_config.name
    assert payload["firecrest.username"] == auth.username
    assert "error.path" in payload  # Filesystem health check does have a filesystem path


async def test_health_check_s3_failure_logs_error(
    slurm_cluster_with_ssh_config,
    caplog,
):
    s3_check = S3HealthCheck(
        data_transfer=slurm_cluster_with_ssh_config.data_operation.data_transfer,
        timeout=10,
    )

    with patch.object(
        S3HealthCheck,
        "execute_check",
        new_callable=AsyncMock,
        side_effect=ConnectionError("S3 connection refused"),
    ):
        with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
            health = await s3_check.check()

    record = caplog.records[0]
    payload = ast.literal_eval(record.getMessage())

    assert health.healthy is False
    assert payload["message"] == "Health check failed"
    assert payload["error.service"] == BackendServiceType.external_storage.value
    assert "error.system" not in payload  # S3 health check does not have a system name
    assert "error.path" not in payload  # S3 health check does not have a filesystem path
    assert "firecrest.username" not in payload  # S3 health check does not have a username
