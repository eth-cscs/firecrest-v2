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
from tests import mocked_api_responses


@pytest.fixture(scope="module")
def mocked_nodes_get_response():
    response_file = impresources.files(mocked_api_responses) / "slurm_get_nodes.json"
    with response_file.open("r") as response:
        return json.load(response)


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
