# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import json
from datetime import datetime, timezone
from contextlib import contextmanager
from importlib import resources as impresources
from unittest.mock import AsyncMock, patch

import pytest
from aioresponses import aioresponses
from pydantic import ValidationError

from firecrest.config import (
    BackendServiceType,
    NodesServiceHealth,
    ProbingService,
    ProbingServices,
)
from firecrest.status.health_check.health_checker_cluster import ClusterHealthChecker
from firecrest.status.models import GetNodesResponse
from lib.scheduler_clients.models import NodeModel
from tests import mocked_api_responses
from tests.health_check_test import TokenDecoderMock, mocked_token_response


@pytest.fixture(scope="module")
def mocked_nodes_get_response():
    response_file = impresources.files(mocked_api_responses) / "slurm_get_nodes.json"
    with response_file.open("r") as response:
        return json.load(response)


def nodes_url(cluster):
    return "{root_url}/slurm/v{version}/nodes".format(
        root_url=cluster.scheduler.api_url,
        version=cluster.scheduler.api_version,
    )


@contextmanager
def nodes_probing(cluster, use_as_cache: bool, health=None, only_nodes=False):
    """Temporarily enable the nodes probe (and optionally its health) on a cluster."""
    original_services = cluster.probing.services
    original_health = cluster.servicesHealth
    services = {} if only_nodes else dict(original_services or {})
    services[BackendServiceType.nodes] = ProbingService(use_as_cache=use_as_cache)
    cluster.probing.services = services
    if health is not None:
        cluster.servicesHealth = list(original_health or []) + [health]
    try:
        yield
    finally:
        cluster.probing.services = original_services
        cluster.servicesHealth = original_health


CACHED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def cached_health(nodes, healthy=True):
    health = NodesServiceHealth(service_type=BackendServiceType.nodes)
    health.healthy = healthy
    health.nodes = nodes
    health.last_checked = CACHED_AT
    return health


def test_use_as_cache_only_allowed_on_nodes():
    ProbingServices(services={"nodes": {"use_as_cache": True}})
    with pytest.raises(ValidationError):
        ProbingServices(services={"scheduler": {"use_as_cache": True}})


async def test_nodes_health_check_stores_nodes(
    mocked_nodes_get_response, slurm_cluster_with_api_config
):
    cluster = slurm_cluster_with_api_config
    with nodes_probing(cluster, use_as_cache=True, only_nodes=True), aioresponses() as mocked, patch(
        "firecrest.status.health_check.health_checker_cluster.AsyncOAuth2Client.fetch_token",
        new=AsyncMock(return_value=mocked_token_response()),
    ):
        mocked.get(nodes_url(cluster), status=200, repeat=True,
                   body=json.dumps(mocked_nodes_get_response))
        await ClusterHealthChecker(cluster, token_decoder=TokenDecoderMock()).check()

        health = [s for s in cluster.servicesHealth if isinstance(s, NodesServiceHealth)]
        assert len(health) == 1
        assert health[0].healthy
        assert len(health[0].nodes) == 1
        assert health[0].last_checked is not None
        # nodes are kept in memory but not exposed in the health report
        assert "nodes" not in health[0].model_dump(by_alias=True)


async def test_nodes_health_check_failure(slurm_cluster_with_api_config):
    cluster = slurm_cluster_with_api_config
    with nodes_probing(cluster, use_as_cache=True, only_nodes=True), aioresponses() as mocked, patch(
        "firecrest.status.health_check.health_checker_cluster.AsyncOAuth2Client.fetch_token",
        new=AsyncMock(return_value=mocked_token_response()),
    ):
        mocked.get(nodes_url(cluster), status=500, repeat=True, body="{}")
        await ClusterHealthChecker(cluster, token_decoder=TokenDecoderMock()).check()

        health = [s for s in cluster.servicesHealth if isinstance(s, NodesServiceHealth)]
        assert len(health) == 1
        assert not health[0].healthy
        assert health[0].nodes is None


def test_nodes_served_from_cache(client, slurm_cluster_with_api_config):
    cluster = slurm_cluster_with_api_config
    cached = [NodeModel(name="cached-node", cpus=4, state=["IDLE"])]
    with nodes_probing(cluster, True, cached_health(cached)), aioresponses() as mocked:
        response = client.get(f"/status/{cluster.name}/nodes")
        assert response.status_code == 200
        nodes = GetNodesResponse(**response.json())
        assert [n.name for n in nodes.nodes] == ["cached-node"]
        assert nodes.cached_at == CACHED_AT
        # the scheduler was not queried
        assert len(mocked.requests) == 0


@pytest.mark.parametrize(
    "use_as_cache,health",
    [
        (False, cached_health([NodeModel(name="cached-node", cpus=4, state=["IDLE"])])),
        (True, None),
        (True, cached_health(None, healthy=False)),
    ],
    ids=["cache-disabled", "no-cached-data", "last-check-failed"],
)
def test_nodes_not_served_from_cache(
    client, mocked_nodes_get_response, slurm_cluster_with_api_config,
    use_as_cache, health,
):
    cluster = slurm_cluster_with_api_config
    with nodes_probing(cluster, use_as_cache, health), aioresponses() as mocked:
        mocked.get(nodes_url(cluster), status=200,
                   body=json.dumps(mocked_nodes_get_response))
        response = client.get(f"/status/{cluster.name}/nodes")
        assert response.status_code == 200
        nodes = GetNodesResponse(**response.json())
        assert "cached-node" not in [n.name for n in nodes.nodes]
        assert response.json()["cachedAt"] is None
        assert len(mocked.requests) == 1
