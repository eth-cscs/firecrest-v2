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
def mocked_ssh_qsub_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_qsub_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_qstat_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_qstat_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_qstat_allusers_output():
    output_file = (
        impresources.files(mocked_ssh_outputs) / "ssh_qstat_allusers_command.json"
    )
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_qdel_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_qdel_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_pbsnodes_output():
    output_file = impresources.files(mocked_ssh_outputs) / "ssh_pbsnodes_command.json"
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_qstat_partitions_output():
    output_file = (
        impresources.files(mocked_ssh_outputs) / "ssh_qstat_partitions_command.json"
    )
    with output_file.open("rb") as output:
        return json.load(output)


async def test_submit_job(client, ssh_client, mocked_ssh_qsub_output, pbs_cluster):

    request_body = {
        "job": {
            "name": "test1",
            "working_directory": "/home/test1",
            "env": {"PATH": "/bin:/usr/bin/:/usr/local/bin/"},
            "script": "#!/bin/bash\nfactor $(od -N 10 -t uL -An /dev/urandom | tr -d ' ')",
        }
    }

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_qsub_output)]):
        response = client.post(
            "/compute/{cluster_name}/jobs".format(cluster_name=pbs_cluster.name),
            json=request_body,
        )
        assert response.status_code == 201
        assert response.json() is not None


async def test_get_job(client, ssh_client, mocked_ssh_qstat_output, pbs_cluster):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_qstat_output)]):
        response = client.get(
            "/compute/{cluster_name}/jobs/{job_id}".format(
                cluster_name=pbs_cluster.name, job_id=1
            )
        )
        assert response.status_code == 200
        assert response.json() is not None

        assert response.json()["jobs"][0]["jobId"] == 1
        assert response.json()["jobs"][0]["status"]["exitCode"] == 0


async def test_get_jobs_allusers(
    client, ssh_client, mocked_ssh_qstat_allusers_output, pbs_cluster
):
    async with ssh_client.mocked_output(
        [MockedCommand(**mocked_ssh_qstat_allusers_output)]
    ):
        response = client.get(
            "/compute/{cluster_name}/jobs?allusers=true".format(
                cluster_name=pbs_cluster.name
            )
        )
        assert response.status_code == 200
        assert response.json() is not None

        assert response.json()["jobs"][0]["user"] == "fireuser"
        assert response.json()["jobs"][1]["user"] == "fireuser"
        assert response.json()["jobs"][2]["user"] == "firesrv"


async def test_get_job_metadata(
    client,
    ssh_client,
    mocked_ssh_qstat_output,
    pbs_cluster,
):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_qstat_output)]):
        response = client.get(
            "/compute/{cluster_name}/jobs/{job_id}/metadata".format(
                cluster_name=pbs_cluster.name, job_id=1
            )
        )
        assert response.status_code == 200
        assert response.json() is not None


async def test_delete_job(client, ssh_client, mocked_ssh_qdel_output, pbs_cluster):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_qdel_output)]):
        response = client.delete(
            "/compute/{cluster_name}/jobs/{job_id}".format(
                cluster_name=pbs_cluster.name, job_id=1
            )
        )
        assert response.status_code == 204


async def test_get_nodes(client, ssh_client, mocked_ssh_pbsnodes_output, pbs_cluster):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_pbsnodes_output)]):
        response = client.get(
            "/status/{cluster_name}/nodes".format(cluster_name=pbs_cluster.name)
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert response.json()["nodes"] is not None


async def test_get_partitions(
    client, ssh_client, mocked_ssh_qstat_partitions_output, pbs_cluster
):

    async with ssh_client.mocked_output(
        [MockedCommand(**mocked_ssh_qstat_partitions_output)]
    ):
        response = client.get(
            "/status/{cluster_name}/partitions".format(cluster_name=pbs_cluster.name)
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert response.json()["partitions"] is not None
