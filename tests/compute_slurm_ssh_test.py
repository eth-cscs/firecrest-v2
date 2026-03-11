# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from importlib import resources as impresources
import pytest
from tests import mocked_ssh_outputs
import json

from tests.mock_ssh_client import MockedCommand


@pytest.fixture(scope="module")
def mocked_ssh_sbatch_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_sbatch_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_sacct_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_sacct_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_squeue_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_squeue_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_squeue_allusers_output():
    output_file = (
        impresources.files(mocked_ssh_outputs) / "ssh_squeue_allusers_command.json"
    )
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_sacct_allusers_output():
    output_file = (
        impresources.files(mocked_ssh_outputs) / "ssh_sacct_allusers_command.json"
    )
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_sacct_script_output():
    output_file = (
        impresources.files(mocked_ssh_outputs) / "ssh_sacct_batch_script_command.json"
    )
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_scontrol_script_output():
    output_file = (
        impresources.files(mocked_ssh_outputs) / "ssh_scontrol_script_command.json"
    )
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_scontrol_job_output():
    output_file = (
        impresources.files(mocked_ssh_outputs) / "ssh_scontrol_job_command.json"
    )
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_scancel_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_scancel_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_sinfo_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_sinfo_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


async def test_submit_job(
    client, ssh_client, mocked_ssh_sbatch_output, slurm_cluster_with_ssh_config
):

    request_body = {
        "job": {
            "name": "test1",
            "working_directory": "/home/test1",
            "env": {"PATH": "/bin:/usr/bin/:/usr/local/bin/"},
            "script": "#!/bin/bash\nfactor $(od -N 10 -t uL -An /dev/urandom | tr -d ' ')",
        }
    }

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_sbatch_output)]):
        response = client.post(
            "/compute/{cluster_name}/jobs".format(
                cluster_name=slurm_cluster_with_ssh_config.name
            ),
            json=request_body,
        )
        assert response.status_code == 201
        assert response.json() is not None


async def test_get_job(
    client,
    ssh_client,
    mocked_ssh_sacct_output,
    mocked_ssh_squeue_output,
    slurm_cluster_with_ssh_config,
):

    async with ssh_client.mocked_output(
        [
            MockedCommand(**mocked_ssh_sacct_output),
            MockedCommand(**mocked_ssh_squeue_output),
        ]
    ):
        response = client.get(
            "/compute/{cluster_name}/jobs/{job_id}".format(
                cluster_name=slurm_cluster_with_ssh_config.name, job_id=1
            )
        )
        assert response.status_code == 200
        assert response.json() is not None

        assert response.json()["jobs"][0]["status"]["exitCode"] == 0


async def test_get_jobs_allusers(
    client,
    ssh_client,
    mocked_ssh_sacct_allusers_output,
    mocked_ssh_squeue_allusers_output,
    slurm_cluster_with_ssh_config,
):
    async with ssh_client.mocked_output(
        [
            MockedCommand(**mocked_ssh_sacct_allusers_output),
            MockedCommand(**mocked_ssh_squeue_allusers_output),
        ]
    ):
        response = client.get(
            "/compute/{cluster_name}/jobs?allusers=true".format(
                cluster_name=slurm_cluster_with_ssh_config.name
            )
        )
        assert response.status_code == 200
        assert response.json() is not None

        assert response.json()["jobs"][0]["user"] == "fireuser"
        assert response.json()["jobs"][1]["user"] == "firesrv"


async def test_get_job_metadata(
    client,
    ssh_client,
    mocked_ssh_sacct_output,
    mocked_ssh_sacct_script_output,
    mocked_ssh_scontrol_script_output,
    mocked_ssh_scontrol_job_output,
    slurm_cluster_with_ssh_config,
):

    async with ssh_client.mocked_output(
        [
            MockedCommand(**mocked_ssh_sacct_output),
            MockedCommand(**mocked_ssh_sacct_script_output),
            MockedCommand(**mocked_ssh_scontrol_script_output),
            MockedCommand(**mocked_ssh_scontrol_job_output),
        ]
    ):
        response = client.get(
            "/compute/{cluster_name}/jobs/{job_id}/metadata".format(
                cluster_name=slurm_cluster_with_ssh_config.name, job_id=1
            )
        )
        assert response.status_code == 200
        assert response.json() is not None


async def test_delete_job(
    client, ssh_client, mocked_ssh_scancel_output, slurm_cluster_with_ssh_config
):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_scancel_output)]):
        response = client.delete(
            "/compute/{cluster_name}/jobs/{job_id}".format(
                cluster_name=slurm_cluster_with_ssh_config.name, job_id=1
            )
        )
        assert response.status_code == 204


async def test_get_sinfo(
    client, ssh_client, mocked_ssh_sinfo_output, slurm_cluster_with_ssh_config
):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_sinfo_output)]):
        response = client.get(
            "/status/{cluster_name}/nodes".format(
                cluster_name=slurm_cluster_with_ssh_config.name
            )
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert response.json()["nodes"] is not None
