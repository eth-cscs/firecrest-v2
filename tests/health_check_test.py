# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from importlib import resources as impresources
from firecrest.plugins import settings
import json
import pytest
from aioresponses import aioresponses
from pytest_httpx import HTTPXMock
from firecrest.status.health_check.health_checker_cluster import ClusterHealthChecker
from lib.auth.authN.OIDC_token_auth import OIDCTokenAuth
from lib.models.apis.api_auth_model import ApiAuthModel
from tests.mock_ssh_client import MockedCommand
from tests import mocked_api_responses

# import helpers functions to avoid duplicating code in tests
from tests.helpers import (
    mocked_ssh_ls_output,
    helper_test_userinfo,
    helper_test_get_job,
    helper_test_ls_command,
    load_ssh_output,
)


@pytest.fixture(scope="module")
def mocked_ssh_id_output():
    return load_ssh_output("ssh_id_command.json")


@pytest.fixture(scope="module")
def mocked_nodes_get_response():
    response_file = impresources.files(mocked_api_responses) / "slurm_get_nodes.json"
    with response_file.open("r") as response:
        return json.load(response)

@pytest.fixture(scope="module")
def mocked_unhealthy_filesystem_response():
    response_file = impresources.files(mocked_api_responses) / "f7t_filesystem_not_healthy.json"
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
    assert "s3" in slurm_cluster_with_ssh_no_health_check_config.probing.services

    # ssh, scheduler and filesystem probing are not configured
    assert "ssh" not in slurm_cluster_with_ssh_no_health_check_config.probing.services
    assert "scheduler" not in slurm_cluster_with_ssh_no_health_check_config.probing.services
    assert "filesystem" not in slurm_cluster_with_ssh_no_health_check_config.probing.services


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


async def test_health_check_disabled_ok_with_filesystem(
        client, ssh_client, mocked_ssh_ls_wrong_path_output,
        slurm_cluster_with_ssh_no_health_check_config,):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_ls_wrong_path_output)]):

        response = client.get(
            "/filesystem/{cluster_name}/ops/ls?path={path}".format(
                cluster_name=slurm_cluster_with_ssh_no_health_check_config.name, path="/wrong_path"
            )
        )

        assert response.status_code == 404
        assert response.json() is not None


async def test_health_check_disabled_ok_with_no_filesystem(
        client, ssh_client,
        slurm_cluster_with_ssh_no_health_check_config,):

    await helper_test_ls_command(client, ssh_client,
                                 slurm_cluster_with_ssh_no_health_check_config.name)


async def test_health_check_disabled_not_ok_transversal(
        client, ssh_client,
        slurm_cluster_with_ssh_no_health_check_config,):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_ls_output())]):

        response = client.get(
            "/filesystem/{cluster_name}/ops/ls?path={path}".format(
                cluster_name=slurm_cluster_with_ssh_no_health_check_config.name, path="/home/../etc/passwd"
            )
        )

        assert response.status_code == 400
        assert response.json() is not None
