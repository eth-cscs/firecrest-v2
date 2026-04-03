# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# Add src folder to python paths
import json

import aiohttp

from firecrest.status.models import (
    GetNodesResponse,
    GetPartitionsResponse,
    GetReservationsResponse,
    UserInfoResponse,
)

from importlib import resources as impresources
from tests import mocked_api_responses
from tests.mock_ssh_client import MockedCommand

import pytest
from aioresponses import aioresponses

from firecrest.config import HPCCluster, Scheduler
from tests.filesystem_ops_test import load_ssh_output


@pytest.fixture(scope="module")
def mocked_get_nodes_response():
    response_file = impresources.files(mocked_api_responses) / "slurm_get_nodes.json"
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_get_resrvations_response():
    response_file = (
        impresources.files(mocked_api_responses) / "slurm_get_reservations.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_get_partitions_response():
    response_file = (
        impresources.files(mocked_api_responses) / "slurm_get_partitions.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_ssh_id_recursive_output():
    return load_ssh_output("ssh_id_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_reservation_output():
    return load_ssh_output("ssh_scontrol_reservation_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_default_account_output():
    return load_ssh_output("ssh_sacctmgr_default_account.json")


@pytest.fixture(scope="module")
def mocked_ssh_accounts_output():
    return load_ssh_output("ssh_sacctmgr_accounts.json")


@pytest.fixture(scope="module")
def cluster():
    scheduler = Scheduler(
        type="Slurm", api_url="http://192.168.240.2:6820", api_version="0.0.38"
    )
    return HPCCluster(
        name="cluster-api", scheduler=scheduler, host="192.168.240.2", ssh_port=22
    )


def test_systems_nodes(
    client, mocked_get_nodes_response, slurm_cluster_with_api_config
):

    with aioresponses() as mocked:
        mocked.get(
            "{root_url}/slurm/v{version}/nodes".format(
                root_url=slurm_cluster_with_api_config.scheduler.api_url,
                version=slurm_cluster_with_api_config.scheduler.api_version,
            ),
            status=200,
            body=json.dumps(mocked_get_nodes_response),
        )

        response = client.get(
            "/status/{cluster_namne}/nodes".format(
                cluster_namne=slurm_cluster_with_api_config.name
            )
        )
        assert response.status_code == 200
        assert response.json() is not None
        nodes = GetNodesResponse(**response.json())
        assert len(nodes.nodes) == 1
        timeout = aiohttp.ClientTimeout(
            total=slurm_cluster_with_api_config.scheduler.timeout
        )
        mocked.assert_called_once_with(
            "{root_url}/slurm/v{version}/nodes".format(
                root_url=slurm_cluster_with_api_config.scheduler.api_url,
                version=slurm_cluster_with_api_config.scheduler.api_version,
            ),
            method="GET",
            headers={
                "Content-Type": "application/json",
                "X-SLURM-USER-NAME": "test-user",
                "X-SLURM-USER-TOKEN": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlcm5hbWUiOiJ0ZXN0IiwicHJlZmZlcmVkLXVzZXJuYW1lIjoidGVzdCJ9.9lEMnYRwLVeOTQKoXxzMd81zJNOAEnrDI3QtcJsUi7A",
            },
            timeout=timeout,
        )


def test_systems_partitions(
    client, mocked_get_partitions_response, slurm_cluster_with_api_config
):

    with aioresponses() as mocked:
        mocked.get(
            "{root_url}/slurm/v{version}/partitions".format(
                root_url=slurm_cluster_with_api_config.scheduler.api_url,
                version=slurm_cluster_with_api_config.scheduler.api_version,
            ),
            status=200,
            body=json.dumps(mocked_get_partitions_response),
        )

        response = client.get(
            "/status/{cluster_namne}/partitions".format(
                cluster_namne=slurm_cluster_with_api_config.name
            )
        )
        assert response.status_code == 200
        assert response.json() is not None
        partitions = GetPartitionsResponse(**response.json())
        assert len(partitions.partitions) == 3
        timeout = aiohttp.ClientTimeout(
            total=slurm_cluster_with_api_config.scheduler.timeout
        )
        mocked.assert_called_once_with(
            "{root_url}/slurm/v{version}/partitions".format(
                root_url=slurm_cluster_with_api_config.scheduler.api_url,
                version=slurm_cluster_with_api_config.scheduler.api_version,
            ),
            method="GET",
            headers={
                "Content-Type": "application/json",
                "X-SLURM-USER-NAME": "test-user",
                "X-SLURM-USER-TOKEN": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlcm5hbWUiOiJ0ZXN0IiwicHJlZmZlcmVkLXVzZXJuYW1lIjoidGVzdCJ9.9lEMnYRwLVeOTQKoXxzMd81zJNOAEnrDI3QtcJsUi7A",
            },
            timeout=timeout,
        )


def test_systems_reservations(
    client, mocked_get_resrvations_response, slurm_cluster_with_api_config
):

    with aioresponses() as mocked:
        mocked.get(
            "{root_url}/slurm/v{version}/reservations".format(
                root_url=slurm_cluster_with_api_config.scheduler.api_url,
                version=slurm_cluster_with_api_config.scheduler.api_version,
            ),
            status=200,
            body=json.dumps(mocked_get_resrvations_response),
        )

        response = client.get(
            "/status/{cluster_namne}/reservations".format(
                cluster_namne=slurm_cluster_with_api_config.name
            )
        )
        assert response.status_code == 200
        assert response.json() is not None
        reservations = GetReservationsResponse(**response.json())
        assert len(reservations.reservations) == 1
        timeout = aiohttp.ClientTimeout(
            total=slurm_cluster_with_api_config.scheduler.timeout
        )
        mocked.assert_called_once_with(
            "{root_url}/slurm/v{version}/reservations".format(
                root_url=slurm_cluster_with_api_config.scheduler.api_url,
                version=slurm_cluster_with_api_config.scheduler.api_version,
            ),
            method="GET",
            headers={
                "Content-Type": "application/json",
                "X-SLURM-USER-NAME": "test-user",
                "X-SLURM-USER-TOKEN": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlcm5hbWUiOiJ0ZXN0IiwicHJlZmZlcmVkLXVzZXJuYW1lIjoidGVzdCJ9.9lEMnYRwLVeOTQKoXxzMd81zJNOAEnrDI3QtcJsUi7A",
            },
            timeout=timeout,
        )


async def test_userinfo(
    client,
    ssh_client,
    mocked_ssh_id_recursive_output,
    mocked_ssh_default_account_output,
    mocked_ssh_accounts_output,
    slurm_cluster_with_ssh_config,
):

    async with ssh_client.mocked_output(
        [
            MockedCommand(**mocked_ssh_id_recursive_output),
            MockedCommand(**mocked_ssh_default_account_output),
            MockedCommand(**mocked_ssh_accounts_output),
        ]
    ):
        response = client.get(f"/status/{slurm_cluster_with_ssh_config.name}/userinfo")
        assert response.status_code == 200
        assert UserInfoResponse(**response.json()) is not None


async def test_ssh_reservation(
    client, ssh_client, mocked_ssh_reservation_output, slurm_cluster_with_ssh_config
):

    async with ssh_client.mocked_output(
        [MockedCommand(**mocked_ssh_reservation_output)]
    ):
        response = client.get(
            f"/status/{slurm_cluster_with_ssh_config.name}/reservations"
        )
        assert response.status_code == 200


async def test_liveness_check(client):

    response = client.get("/status/liveness")
    assert response.status_code == 200
