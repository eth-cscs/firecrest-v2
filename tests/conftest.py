# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from datetime import datetime
from firecrest.dependencies import (
    APIAuthDependency,
    S3ClientConnectionType,
    S3ClientDependency,
    SSHClientDependency,
    SchedulerClientDependency,
)
from tests.mock_ssh_client import MockSSHClientPool

from firecrest.plugins import settings

from fastapi.testclient import TestClient

# configs
from firecrest.config import get_settings

# request vars
from lib.request_vars import g

# models
from lib.models import ApiAuthUser, ApiAuthType

# app
from firecrest.main import create_app
from aiobotocore.session import get_session
from aiobotocore.config import AioConfig


import pytest


class OverrideAPIAuthDependency:
    def __init__(self):
        pass

    async def __call__(self):
        user = ApiAuthUser(
            type=ApiAuthType.user,
            token={"username": "test-user", "preferred_username": "test-user"},
            username="test-user",
            email="test-user@cscs.ch",
            first_name="Test",
            last_name="User",
            active=True,
        )
        g().auth = user
        g().access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlcm5hbWUiOiJ0ZXN0IiwicHJlZmZlcmVkLXVzZXJuYW1lIjoidGVzdCJ9.9lEMnYRwLVeOTQKoXxzMd81zJNOAEnrDI3QtcJsUi7A"
        return user


# Instantiate a globla mock s3_client to be used as fixture and
# for FASTApi dependency injection
global_s3_client = None


@pytest.fixture(scope="session", autouse=True)
async def s3_client():
    global global_s3_client
    async with get_session().create_client(
        "s3",
        region_name=settings.storage.region,
        aws_secret_access_key=settings.storage.secret_access_key,
        aws_access_key_id=settings.storage.access_key_id,
        endpoint_url=settings.storage.private_url,
        config=AioConfig(signature_version="s3v4"),
    ) as client:
        global_s3_client = client
        yield global_s3_client


class OverrideS3ClientDependency:
    def __init__(
        self, connection: S3ClientConnectionType = S3ClientConnectionType.public
    ):
        pass

    async def __call__(self):
        global global_s3_client
        yield global_s3_client


# Instantiate a globla mock ssh_client to be used as fixture and
# for FASTApi dependency injection

global_ssh_client = None


@pytest.fixture(scope="session", autouse=True)
async def ssh_client():
    global global_ssh_client
    global_ssh_client = MockSSHClientPool()
    yield global_ssh_client


class OverrideSSHClientPool:
    def __init__(self):
        pass

    async def __call__(self, system_name: str):
        global global_ssh_client
        yield global_ssh_client


class OverrideSchedulerClient(SchedulerClientDependency):

    async def _get_ssh_client(self, system_name):
        return global_ssh_client


@pytest.fixture(scope="module")
def slurm_cluster_with_api_config():
    for cluster in settings.clusters:
        if cluster.scheduler.api_url is not None:
            return cluster


@pytest.fixture(scope="module")
def slurm_cluster_with_ssh_config():
    for cluster in settings.clusters:
        if cluster.scheduler.api_url is None:
            return cluster


@pytest.fixture(scope="session", autouse=True)
def app():
    settings = get_settings()

    app = create_app(settings=settings)
    yield app


@pytest.fixture(scope="session", autouse=True)
def client(app, s3_client, ssh_client):

    # Ensures s3_client and ssh_client are instantiated before dependency override
    assert s3_client is not None
    assert ssh_client is not None

    app.dependency_overrides[APIAuthDependency()] = OverrideAPIAuthDependency()
    app.dependency_overrides[
        S3ClientDependency(connection=S3ClientConnectionType.public)
    ] = OverrideS3ClientDependency(connection=S3ClientConnectionType.public)
    app.dependency_overrides[
        S3ClientDependency(connection=S3ClientConnectionType.private)
    ] = OverrideS3ClientDependency(connection=S3ClientConnectionType.private)

    app.dependency_overrides[SSHClientDependency()] = OverrideSSHClientPool()
    app.dependency_overrides[SchedulerClientDependency()] = OverrideSchedulerClient()
    app.dependency_overrides[SchedulerClientDependency(ignore_health=True)] = (
        OverrideSchedulerClient(ignore_health=True)
    )

    client = TestClient(app)
    yield client


@pytest.fixture(scope="session", autouse=True)
def set_up_cluster_health():
    settings = get_settings()
    for cluster in settings.clusters:
        health = [
            {
                "serviceType": "scheduler",
                "lastChecked": datetime.now(),
                "latency": 0,
                "healthy": True,
            },
            {
                "serviceType": "ssh",
                "lastChecked": datetime.now(),
                "latency": 0,
                "healthy": True,
            },
            {
                "serviceType": "filesystem",
                "lastChecked": datetime.now(),
                "latency": 0,
                "healthy": True,
                "path": "/home",
            },
        ]
        cluster.servicesHealth = health
