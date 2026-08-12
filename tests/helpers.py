# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from importlib import resources as impresources
import json

from tests import mocked_ssh_outputs
from tests.mock_ssh_client import MockedCommand
from firecrest.status.models import UserInfoResponse


def load_ssh_output(file: str):
    output_file = impresources.files(mocked_ssh_outputs) / file
    with output_file.open("rb") as output:
        return json.load(output, strict=False)


def mocked_ssh_ls_output():
    return load_ssh_output("ssh_ls_command.json")


def mocked_ssh_sacct_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_sacct_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


def mocked_ssh_squeue_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_squeue_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


def mocked_ssh_id_recursive_output():
    return load_ssh_output("ssh_id_command.json")


def mocked_ssh_default_account_output():
    return load_ssh_output("ssh_sacctmgr_default_account.json")


def mocked_ssh_accounts_output():
    return load_ssh_output("ssh_sacctmgr_accounts.json")


# Test helper functions

async def helper_test_userinfo(
    client,
    ssh_client,
    cluster_name: str,    
):

    async with ssh_client.mocked_output(
        [
            MockedCommand(**mocked_ssh_id_recursive_output()),
            MockedCommand(**mocked_ssh_default_account_output()),
            MockedCommand(**mocked_ssh_accounts_output()),
        ]
    ):
        response = client.get(f"/status/{cluster_name}/userinfo")
        assert response.status_code == 200
        assert UserInfoResponse(**response.json()) is not None


async def helper_test_get_job(
    client,
    ssh_client,
    cluster_name: str,
):

    async with ssh_client.mocked_output(
        [
            MockedCommand(**mocked_ssh_sacct_output()),
            MockedCommand(**mocked_ssh_squeue_output()),
        ]
    ):
        response = client.get(f"/compute/{cluster_name}/jobs/1")

        assert response.status_code == 200
        assert response.json() is not None

        assert response.json()["jobs"][0]["status"]["exitCode"] == 0


async def helper_test_ls_command(client,
                                 ssh_client,
                                 cluster_name="cluster-slurm-ssh",
                                 path="/home"):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_ls_output())]):

        response = client.get(
            f"/filesystem/{cluster_name}/ops/ls?path={path}"
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert len(response.json()["output"]) == 4
