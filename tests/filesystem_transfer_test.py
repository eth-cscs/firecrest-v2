# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# Add src folder to python paths
import json

from firecrest.filesystem.transfer.models import (
    CopyResponse,
    DeleteResponse,
    DownloadFileResponse,
    MoveResponse,
    UploadFileResponse,
    CompressResponse,
    ExtractResponse,
)

from importlib import resources as impresources
from tests import mocked_api_responses

import pytest
from botocore.stub import Stubber
from aioresponses import aioresponses
from tests import mocked_ssh_outputs
from tests.mock_ssh_client import MockedCommand


def load_ssh_output(file: str):
    output_file = impresources.files(mocked_ssh_outputs) / file
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_job_submit_response():
    response_file = impresources.files(mocked_api_responses) / "slurm_submit_job.json"
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
async def mocked_create_bucket_response():
    response_file = impresources.files(mocked_api_responses) / "s3_create_bucket.json"
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
async def mocked_put_bucket_lifecycle_configuration():
    response_file = (
        impresources.files(mocked_api_responses)
        / "s3_put_bucket_lifecycle_configuration.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
async def mocked_create_multipart_upload():
    response_file = (
        impresources.files(mocked_api_responses) / "s3_create_multipart_upload.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_ssh_stat_output():
    return load_ssh_output("ssh_stat_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_id_output():
    return load_ssh_output("ssh_id_command.json")


@pytest.mark.asyncio
async def test_upload(
    client,
    s3_client,
    ssh_client,
    slurm_cluster_with_api_config,
    mocked_job_submit_response,
    mocked_create_bucket_response,
    mocked_create_multipart_upload,
    mocked_put_bucket_lifecycle_configuration,
    mocked_ssh_id_output,
):

    request_body = {
        "path": "/home/test1/",
        "account": "fireuser",
        "transfer_directives": {
            "transfer_method": "s3",
            "fileName": "data.big",
            "fileSize": "100000",
        },
    }
    # mocking s3 server response
    with Stubber(s3_client) as stubber:
        stubber.add_response(
            method="create_bucket",
            service_response=mocked_create_bucket_response,
            expected_params={"Bucket": "test-user"},
        )
        stubber.add_response(
            method="put_bucket_lifecycle_configuration",
            service_response=mocked_put_bucket_lifecycle_configuration,
        )
        stubber.add_response(
            method="create_multipart_upload",
            service_response=mocked_create_multipart_upload,
        )
        stubber.activate()

        # mocking slurm server response
        with aioresponses() as mocked:

            mocked.post(
                f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
                status=200,
                body=json.dumps(mocked_job_submit_response),
            )
            async with ssh_client.mocked_output(
                [
                    MockedCommand(**mocked_ssh_id_output),
                ]
            ):
                # Testing storage end-point
                response = client.post(
                    f"/filesystem/{slurm_cluster_with_api_config.name}/transfer/upload",
                    json=request_body,
                )
            assert response.status_code == 201
            assert response.json() is not None
            upload = UploadFileResponse(**response.json())
            assert upload.transfer_directives.parts_upload_urls is not None
            assert upload.transfer_directives.complete_upload_url is not None
            assert upload.transfer_job.job_id == mocked_job_submit_response["job_id"]
            assert upload.transfer_job.system == slurm_cluster_with_api_config.name
        stubber.deactivate()


@pytest.mark.asyncio
async def test_download(
    client,
    s3_client,
    ssh_client,
    slurm_cluster_with_api_config,
    mocked_job_submit_response,
    mocked_create_bucket_response,
    mocked_put_bucket_lifecycle_configuration,
    mocked_ssh_stat_output,
    mocked_ssh_id_output,
    mocked_create_multipart_upload,
):

    request_body = {
        "sourcePath": "/home/test1/data.big",
        "account": "fireuser",
    }
    # mocking s3 server response
    with Stubber(s3_client) as stubber:
        stubber.add_response(
            method="create_bucket",
            service_response=mocked_create_bucket_response,
            expected_params={"Bucket": "test-user"},
        )
        stubber.add_response(
            method="put_bucket_lifecycle_configuration",
            service_response=mocked_put_bucket_lifecycle_configuration,
        )
        stubber.add_response(
            method="create_multipart_upload",
            service_response=mocked_create_multipart_upload,
        )
        stubber.activate()
        # mocking slurm server response
        with aioresponses() as mocked:
            mocked.post(
                f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
                status=200,
                body=json.dumps(mocked_job_submit_response),
            )

            async with ssh_client.mocked_output(
                [
                    MockedCommand(**mocked_ssh_stat_output),
                    MockedCommand(**mocked_ssh_id_output),
                ]
            ):

                # Testing storage end-point
                response = client.post(
                    f"/filesystem/{slurm_cluster_with_api_config.name}/transfer/download",
                    json=request_body,
                )
                assert response.status_code == 201
                assert response.json() is not None
                download: DownloadFileResponse = DownloadFileResponse(**response.json())
                assert download.transfer_directives.download_url is not None
                assert (
                    download.transfer_job.job_id == mocked_job_submit_response["job_id"]
                )
                assert (
                    download.transfer_job.system == slurm_cluster_with_api_config.name
                )
            stubber.deactivate()


@pytest.mark.asyncio
async def test_mv(
    client,
    slurm_cluster_with_api_config,
    mocked_job_submit_response,
):

    request_body = {
        "sourcePath": "/home/test1/file1.txt",
        "targetPath": "/home/test1/file2.txt",
        "account": "fireuser",
    }

    with aioresponses() as mocked:
        mocked.post(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
            status=200,
            body=json.dumps(mocked_job_submit_response),
        )

        # Testing storage end-point
        response = client.post(
            f"/filesystem/{slurm_cluster_with_api_config.name}/transfer/mv",
            json=request_body,
        )
        assert response.status_code == 201
        assert response.json() is not None
        move = MoveResponse(**response.json())

        assert move.transfer_job.job_id == mocked_job_submit_response["job_id"]
        assert move.transfer_job.system == slurm_cluster_with_api_config.name


@pytest.mark.asyncio
async def test_mv_no_account_set(
    client,
    slurm_cluster_with_api_config,
    mocked_job_submit_response,
):

    request_body = {
        "sourcePath": "/home/test1/file1.txt",
        "targetPath": "/home/test1/file2.txt",
    }

    with aioresponses() as mocked:
        mocked.post(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
            status=200,
            body=json.dumps(mocked_job_submit_response),
        )

        # Testing storage end-point
        response = client.post(
            f"/filesystem/{slurm_cluster_with_api_config.name}/transfer/mv",
            json=request_body,
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_cp(
    client,
    slurm_cluster_with_api_config,
    mocked_job_submit_response,
):

    request_body = {
        "sourcePath": "/home/test1/file1.txt",
        "targetPath": "/home/test1/file2.txt",
        "account": "fireuser",
    }

    with aioresponses() as mocked:
        mocked.post(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
            status=200,
            body=json.dumps(mocked_job_submit_response),
        )

        # Testing storage end-point
        response = client.post(
            f"/filesystem/{slurm_cluster_with_api_config.name}/transfer/cp",
            json=request_body,
        )
        assert response.status_code == 201
        assert response.json() is not None
        copy = CopyResponse(**response.json())

        assert copy.transfer_job.job_id == mocked_job_submit_response["job_id"]
        assert copy.transfer_job.system == slurm_cluster_with_api_config.name


@pytest.mark.asyncio
async def test_rm(
    client,
    slurm_cluster_with_api_config,
    mocked_job_submit_response,
):

    with aioresponses() as mocked:
        mocked.post(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
            status=200,
            body=json.dumps(mocked_job_submit_response),
        )

        # Testing storage end-point
        response = client.delete(
            f"/filesystem/{slurm_cluster_with_api_config.name}/transfer/rm?path=/home/new&account=fireuser"
        )
        assert response.status_code == 200
        assert response.json() is not None
        delete = DeleteResponse(**response.json())

        assert delete.transfer_job.job_id == mocked_job_submit_response["job_id"]
        assert delete.transfer_job.system == slurm_cluster_with_api_config.name


@pytest.mark.asyncio
async def test_compress(
    client,
    slurm_cluster_with_api_config,
    mocked_job_submit_response,
):

    request_body = {
        "sourcePath": "/home/test1/file1.txt",
        "targetPath": "/home/test1/file1.tar",
        "account": "fireuser",
        "dereference": False,
    }

    with aioresponses() as mocked:
        mocked.post(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
            status=200,
            body=json.dumps(mocked_job_submit_response),
        )

        # Testing storage end-point
        response = client.post(
            f"/filesystem/{slurm_cluster_with_api_config.name}/transfer/compress",
            json=request_body,
        )
        assert response.status_code == 201
        assert response.json() is not None
        compress = CompressResponse(**response.json())

        assert compress.transfer_job.job_id == mocked_job_submit_response["job_id"]
        assert compress.transfer_job.system == slurm_cluster_with_api_config.name


@pytest.mark.asyncio
async def test_compress_with_pattern(
    client,
    slurm_cluster_with_api_config,
    mocked_job_submit_response,
):

    request_body = {
        "sourcePath": "/home/test1/file1.txt",
        "targetPath": "/home/test1/file1.tar",
        "account": "fireuser",
        "dereference": False,
        "match_pattern": "./[ab].*\\.txt",
    }

    with aioresponses() as mocked:
        mocked.post(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
            status=200,
            body=json.dumps(mocked_job_submit_response),
        )

        # Testing storage end-point
        response = client.post(
            f"/filesystem/{slurm_cluster_with_api_config.name}/transfer/compress",
            json=request_body,
        )
        assert response.status_code == 201
        assert response.json() is not None
        compress = CompressResponse(**response.json())

        assert compress.transfer_job.job_id == mocked_job_submit_response["job_id"]
        assert compress.transfer_job.system == slurm_cluster_with_api_config.name


@pytest.mark.asyncio
async def test_extract(
    client,
    slurm_cluster_with_api_config,
    mocked_job_submit_response,
):

    request_body = {
        "sourcePath": "/home/test1/file1.tar",
        "targetPath": "/home/test1",
        "account": "fireuser",
    }

    with aioresponses() as mocked:
        mocked.post(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
            status=200,
            body=json.dumps(mocked_job_submit_response),
        )

        # Testing storage end-point
        response = client.post(
            f"/filesystem/{slurm_cluster_with_api_config.name}/transfer/extract",
            json=request_body,
        )
        assert response.status_code == 201
        assert response.json() is not None
        compress = ExtractResponse(**response.json())

        assert compress.transfer_job.job_id == mocked_job_submit_response["job_id"]
        assert compress.transfer_job.system == slurm_cluster_with_api_config.name
