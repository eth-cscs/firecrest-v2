# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# Add src folder to python paths
from importlib import resources as impresources

import json
import re
from datetime import datetime, timedelta, timezone

import aiohttp
import pytest
from aioresponses import aioresponses

from tests import mocked_api_responses
from firecrest.compute.models import GetJobResponse, PostJobSubmissionResponse
from lib.scheduler_clients.models import JobsTimeWindow, TIME_WINDOW_DURATIONS
from lib.scheduler_clients.slurm.slurm_rest_client import _time_window_start_time


def _slurmdb_jobs_url_prefix(slurm_cluster_with_api_config):
    return (
        f"{slurm_cluster_with_api_config.scheduler.api_url}/slurmdb/v"
        f"{slurm_cluster_with_api_config.scheduler.api_version}/jobs"
    )


def _get_slurmdb_jobs_query_params(mocked, slurm_cluster_with_api_config):
    # Matching the mock on a query-agnostic URL prefix (see below) means the
    # request's actual query string, whatever param order it used, is only
    # available from aioresponses' recorded call log.
    prefix = _slurmdb_jobs_url_prefix(slurm_cluster_with_api_config)
    matches = [
        url
        for method, url in mocked.requests.keys()
        if method == "GET" and str(url).startswith(prefix)
    ]
    assert len(matches) == 1, f"expected exactly one request to {prefix}, got {matches}"
    return dict(matches[0].query)


def _assert_start_time_matches_window(
    start_time: str, time_window: JobsTimeWindow, tolerance_seconds: int = 15
):
    amount, unit = TIME_WINDOW_DURATIONS[time_window]
    expected = datetime.now(timezone.utc) - timedelta(**{unit: amount})
    assert abs(int(start_time) - int(expected.timestamp())) <= tolerance_seconds


@pytest.fixture(scope="module")
def mocked_job_submit_response():
    response_file = impresources.files(mocked_api_responses) / "slurm_submit_job.json"
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_get_job_response():
    response_file = impresources.files(mocked_api_responses) / "slurm_get_job.json"
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_get_job_from_db_response():
    response_file = (
        impresources.files(mocked_api_responses) / "slurm_get_job_from_db.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_get_jobs_allusers_response():
    response_file = (
        impresources.files(mocked_api_responses) / "slurm_get_allusers_jobs.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_get_jobs_by_name_response():
    response_file = (
        impresources.files(mocked_api_responses) / "slurm_get_jobs_by_name.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_get_jobs_allusers_from_db_response():
    response_file = (
        impresources.files(mocked_api_responses)
        / "slurm_get_allusers_jobs_from_db.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_get_jobs_by_name_from_db_response():
    response_file = (
        impresources.files(mocked_api_responses) / "slurm_get_jobs_by_name_from_db.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_get_job_not_found_response():
    response_file = (
        impresources.files(mocked_api_responses) / "slurm_get_job_not_found.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_get_job_not_found_from_db_response():
    response_file = (
        impresources.files(mocked_api_responses)
        / "slurm_get_job_not_found_from_db.json"
    )
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def mocked_cancel_job_response():
    response_file = impresources.files(mocked_api_responses) / "slurm_cancel_job.json"
    with response_file.open("r") as response:
        return json.load(response)


def test_submit_job(client, mocked_job_submit_response, slurm_cluster_with_api_config):

    request_body = {
        "job": {
            "name": "test1",
            "working_directory": "/home/test1",
            "partition": "partition_a",
            "reservation": "myreservation",
            "script": "#!/bin/bash\nfactor $(od -N 10 -t uL -An /dev/urandom | tr -d ' ')",
        },
    }

    with aioresponses() as mocked:
        mocked.post(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
            status=200,
            body=json.dumps(mocked_job_submit_response),
        )

        response = client.post(
            f"/compute/{slurm_cluster_with_api_config.name}/jobs",
            json=request_body,
        )
        assert response.status_code == 201
        assert response.json() is not None
        job = PostJobSubmissionResponse(**response.json())
        assert job.job_id == mocked_job_submit_response["job_id"]
        timeout = aiohttp.ClientTimeout(
            total=slurm_cluster_with_api_config.scheduler.timeout
        )
        request_body_slurm_api = {
            "job": {
                "name": "test1",
                "reservation": "myreservation",
                "partition": "partition_a",
                "current_working_directory": "/home/test1",
                "environment": ["F7T_version=v2.0.0"],
                "script": "#!/bin/bash\nfactor $(od -N 10 -t uL -An /dev/urandom | tr -d ' ')",
            }
        }

        mocked.assert_called_once_with(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/submit",
            method="POST",
            data=json.dumps(request_body_slurm_api),
            headers={
                "Content-Type": "application/json",
                "X-SLURM-USER-NAME": "test-user",
                "X-SLURM-USER-TOKEN": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlcm5hbWUiOiJ0ZXN0IiwicHJlZmZlcmVkLXVzZXJuYW1lIjoidGVzdCJ9.9lEMnYRwLVeOTQKoXxzMd81zJNOAEnrDI3QtcJsUi7A",
            },
            timeout=timeout,
        )


def test_get_job(
    client,
    mocked_get_job_response,
    mocked_get_job_from_db_response,
    slurm_cluster_with_api_config,
):

    job_id = mocked_get_job_from_db_response["jobs"][0]["job_id"]

    with aioresponses() as mocked:
        mocked.get(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurmdb/v{slurm_cluster_with_api_config.scheduler.api_version}/job/{job_id}",
            status=200,
            body=json.dumps(mocked_get_job_from_db_response),
        )
        mocked.get(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/{job_id}",
            status=200,
            body=json.dumps(mocked_get_job_response),
        )

        response = client.get(
            f"/compute/{slurm_cluster_with_api_config.name}/jobs/{job_id}"
        )
        assert response.status_code == 200
        assert response.json() is not None
        jobs_result = GetJobResponse(**response.json())
        assert jobs_result.jobs[0].job_id == str(job_id)


def test_case_insensitive_system_name(
    client,
    mocked_get_job_from_db_response,
    mocked_get_job_response,
    slurm_cluster_with_api_config,
):

    job_id = mocked_get_job_from_db_response["jobs"][0]["job_id"]

    with aioresponses() as mocked:
        mocked.get(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurmdb/v{slurm_cluster_with_api_config.scheduler.api_version}/job/{job_id}",
            status=200,
            body=json.dumps(mocked_get_job_from_db_response),
        )
        mocked.get(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/{job_id}",
            status=200,
            body=json.dumps(mocked_get_job_response),
        )

        response = client.get(
            f"/compute/{slurm_cluster_with_api_config.name.upper()}/jobs/{job_id}"
        )
        assert response.status_code == 200
        assert response.json() is not None
        jobs_result = GetJobResponse(**response.json())
        assert jobs_result.jobs[0].job_id == str(job_id)


def test_get_job_not_found(
    client,
    mocked_get_job_not_found_response,
    mocked_get_job_not_found_from_db_response,
    slurm_cluster_with_api_config,
):

    job_id = 404

    with aioresponses() as mocked:
        mocked.get(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurmdb/v{slurm_cluster_with_api_config.scheduler.api_version}/job/{job_id}",
            status=200,
            body=json.dumps(mocked_get_job_not_found_from_db_response),
        )
        mocked.get(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/{job_id}",
            status=200,
            body=json.dumps(mocked_get_job_not_found_response),
        )

        response = client.get(
            f"/compute/{slurm_cluster_with_api_config.name}/jobs/{job_id}"
        )
        assert response.status_code == 404
        assert response.json() is not None


async def test_get_jobs_allusers(
    client,
    mocked_get_jobs_allusers_response,
    mocked_get_jobs_allusers_from_db_response,
    slurm_cluster_with_api_config,
):

    with aioresponses() as mocked:
        mocked.get(
            re.compile(
                rf"^{re.escape(_slurmdb_jobs_url_prefix(slurm_cluster_with_api_config))}"
            ),
            status=200,
            body=json.dumps(mocked_get_jobs_allusers_from_db_response),
        )
        mocked.get(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/jobs",
            status=200,
            body=json.dumps(mocked_get_jobs_allusers_response),
        )

        response = client.get(
            f"/compute/{slurm_cluster_with_api_config.name}/jobs?allusers=true"
        )
        assert response.status_code == 200
        assert response.json() is not None
        jobs_result = GetJobResponse(**response.json())
        assert jobs_result.jobs[0].user == "fireuser"
        assert jobs_result.jobs[1].user == "firesrv"

        # no explicit time_window was requested: pin the 24h default
        query_params = _get_slurmdb_jobs_query_params(
            mocked, slurm_cluster_with_api_config
        )
        assert "account" not in query_params
        _assert_start_time_matches_window(
            query_params["start_time"], JobsTimeWindow.LAST_24_HOURS
        )


async def test_get_jobs_with_time_window(
    client,
    mocked_get_jobs_allusers_response,
    mocked_get_jobs_allusers_from_db_response,
    slurm_cluster_with_api_config,
):
    with aioresponses() as mocked:
        mocked.get(
            re.compile(
                rf"^{re.escape(_slurmdb_jobs_url_prefix(slurm_cluster_with_api_config))}"
            ),
            status=200,
            body=json.dumps(mocked_get_jobs_allusers_from_db_response),
        )
        mocked.get(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/jobs",
            status=200,
            body=json.dumps(mocked_get_jobs_allusers_response),
        )

        response = client.get(
            f"/compute/{slurm_cluster_with_api_config.name}/jobs?allusers=true&time_window=7d"
        )
        assert response.status_code == 200
        assert response.json() is not None
        jobs_result = GetJobResponse(**response.json())
        assert jobs_result.jobs[0].user == "fireuser"
        assert jobs_result.jobs[1].user == "firesrv"

        query_params = _get_slurmdb_jobs_query_params(
            mocked, slurm_cluster_with_api_config
        )
        assert "account" not in query_params
        _assert_start_time_matches_window(
            query_params["start_time"], JobsTimeWindow.LAST_7_DAYS
        )


async def test_get_jobs_with_account_and_time_window(
    client,
    mocked_get_jobs_allusers_response,
    mocked_get_jobs_allusers_from_db_response,
    slurm_cluster_with_api_config,
):
    with aioresponses() as mocked:
        mocked.get(
            re.compile(
                rf"^{re.escape(_slurmdb_jobs_url_prefix(slurm_cluster_with_api_config))}"
            ),
            status=200,
            body=json.dumps(mocked_get_jobs_allusers_from_db_response),
        )
        mocked.get(
            re.compile(
                rf"^{re.escape(slurm_cluster_with_api_config.scheduler.api_url)}/slurm/v{re.escape(slurm_cluster_with_api_config.scheduler.api_version)}/jobs"
            ),
            status=200,
            body=json.dumps(mocked_get_jobs_allusers_response),
        )

        response = client.get(
            f"/compute/{slurm_cluster_with_api_config.name}/jobs?account=myaccount&time_window=8h"
        )
        assert response.status_code == 200
        assert response.json() is not None

        query_params = _get_slurmdb_jobs_query_params(
            mocked, slurm_cluster_with_api_config
        )
        assert query_params["account"] == "myaccount"
        _assert_start_time_matches_window(
            query_params["start_time"], JobsTimeWindow.LAST_8_HOURS
        )


async def test_get_jobs_with_invalid_time_window(
    client,
    slurm_cluster_with_api_config,
):
    response = client.get(
        f"/compute/{slurm_cluster_with_api_config.name}/jobs?time_window=30days"
    )
    assert response.status_code == 400


@pytest.mark.parametrize("api_version", ["0.0.38", "0.0.39"])
def test_time_window_start_time_before_epoch_support(api_version):
    start_time = _time_window_start_time(JobsTimeWindow.LAST_24_HOURS, api_version)
    assert start_time == "now-24hours"


@pytest.mark.parametrize(
    "time_window,expected",
    [
        (JobsTimeWindow.LAST_HOUR, "now-1hours"),
        (JobsTimeWindow.LAST_8_HOURS, "now-8hours"),
        (JobsTimeWindow.LAST_24_HOURS, "now-24hours"),
        (JobsTimeWindow.LAST_3_DAYS, "now-3days"),
        (JobsTimeWindow.LAST_7_DAYS, "now-7days"),
    ],
)
def test_time_window_start_time_before_epoch_support_relative_values(
    time_window, expected
):
    assert _time_window_start_time(time_window, "0.0.38") == expected


@pytest.mark.parametrize("api_version", ["0.0.40", "0.0.41", "0.0.42"])
def test_time_window_start_time_with_epoch_support(api_version):
    start_time = _time_window_start_time(JobsTimeWindow.LAST_24_HOURS, api_version)
    assert start_time.isdigit()


async def test_get_jobs_by_name(
    client,
    mocked_get_jobs_by_name_response,
    mocked_get_jobs_by_name_from_db_response,
    slurm_cluster_with_api_config,
):
    with aioresponses() as mocked:

        mocked.get(
            re.compile(
                rf"^{re.escape(_slurmdb_jobs_url_prefix(slurm_cluster_with_api_config))}"
            ),
            status=200,
            body=json.dumps(mocked_get_jobs_by_name_from_db_response),
        )
        mocked.get(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/jobs",
            status=200,
            body=json.dumps(mocked_get_jobs_by_name_response),
        )

        response = client.get(
            f"/compute/{slurm_cluster_with_api_config.name}/jobs?name=NameExists"
        )
        assert response.status_code == 200
        assert response.json() is not None

        jobs_result = GetJobResponse(**response.json())

        assert jobs_result.jobs[0].user == "test-user"
        assert jobs_result.jobs[0].name == "NameExists"


async def test_get_jobs_by_name_not_ok(
    client,
    mocked_get_jobs_by_name_response,
    mocked_get_jobs_by_name_from_db_response,
    slurm_cluster_with_api_config,
):
    with aioresponses() as mocked:

        mocked.get(
            re.compile(
                rf"^{re.escape(_slurmdb_jobs_url_prefix(slurm_cluster_with_api_config))}"
            ),
            status=200,
            body=json.dumps(mocked_get_jobs_by_name_from_db_response),
        )
        mocked.get(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/jobs",
            status=200,
            body=json.dumps(mocked_get_jobs_by_name_response),
        )

        response = client.get(
            f"/compute/{slurm_cluster_with_api_config.name}/jobs?name=DontExist"
        )

        assert response.status_code == 200
        assert len(response.json()["jobs"]) == 0


def test_cancel_job(client, mocked_cancel_job_response, slurm_cluster_with_api_config):

    job_id = 42
    with aioresponses() as mocked:
        mocked.delete(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/{job_id}",
            status=200,
            body=json.dumps(mocked_cancel_job_response),
        )

        response = client.delete(
            f"/compute/{slurm_cluster_with_api_config.name}/jobs/{job_id}"
        )
        assert response.status_code == 204
        timeout = aiohttp.ClientTimeout(
            total=slurm_cluster_with_api_config.scheduler.timeout
        )
        mocked.assert_called_once_with(
            f"{slurm_cluster_with_api_config.scheduler.api_url}/slurm/v{slurm_cluster_with_api_config.scheduler.api_version}/job/{job_id}",
            method="DELETE",
            headers={
                "Content-Type": "application/json",
                "X-SLURM-USER-NAME": "test-user",
                "X-SLURM-USER-TOKEN": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlcm5hbWUiOiJ0ZXN0IiwicHJlZmZlcmVkLXVzZXJuYW1lIjoidGVzdCJ9.9lEMnYRwLVeOTQKoXxzMd81zJNOAEnrDI3QtcJsUi7A",
            },
            timeout=timeout,
        )
