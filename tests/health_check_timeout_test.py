# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from contextlib import asynccontextmanager

import pytest
from pydantic import ValidationError

from firecrest.config import HPCCluster
from firecrest.status.health_check.checks.true_command import TrueCommand
from lib.scheduler_clients.pbs.pbs_client import PbsClient
from lib.scheduler_clients.slurm.slurm_cli_client import SlurmCliClient
from lib.ssh_clients.ssh_client import TimeoutLimitExceeded
from tests.helpers import load_ssh_output
from tests.mock_ssh_client import MockedCommand

# The mocked command answers after DELAY seconds: longer than the SSH client's
# own execute timeout, shorter than the (health check) override.
DELAY = 0.5
CLIENT_TIMEOUT = 0.2
OVERRIDE_TIMEOUT = 2


@asynccontextmanager
async def slow_command(ssh_client, command: MockedCommand):
    original = ssh_client.execute_timeout
    ssh_client.execute_timeout = CLIENT_TIMEOUT
    command.delay = DELAY
    try:
        async with ssh_client.mocked_output([command]):
            yield
    finally:
        ssh_client.execute_timeout = original


async def test_command_execute_timeout_override(ssh_client):
    async with slow_command(ssh_client, MockedCommand(command="true")):
        async with ssh_client.get_client("test", "token") as client:
            with pytest.raises(TimeoutLimitExceeded):
                await client.execute(TrueCommand())

        cmd = TrueCommand()
        cmd.execute_timeout = OVERRIDE_TIMEOUT
        async with ssh_client.get_client("test", "token") as client:
            await client.execute(cmd)


async def test_slurm_cli_get_nodes_timeout(ssh_client):
    sinfo = MockedCommand(**load_ssh_output("ssh_sinfo_command.json"))
    scheduler = SlurmCliClient(ssh_client, "24.11.0")
    async with slow_command(ssh_client, sinfo):
        # regular requests keep the SSH command timeout
        with pytest.raises(TimeoutLimitExceeded):
            await scheduler.get_nodes("test", "token")
        nodes = await scheduler.get_nodes("test", "token", timeout=OVERRIDE_TIMEOUT)
        assert len(nodes) > 0


async def test_slurm_cli_ping_timeout(ssh_client):
    ping = MockedCommand(command="scontrol ping", stdout="Slurmctld(primary) at localhost is UP\n")
    scheduler = SlurmCliClient(ssh_client, "24.11.0")
    async with slow_command(ssh_client, ping):
        with pytest.raises(TimeoutLimitExceeded):
            await scheduler.ping("test", "token")
        await scheduler.ping("test", "token", timeout=OVERRIDE_TIMEOUT)


async def test_pbs_get_nodes_timeout(ssh_client):
    pbsnodes = MockedCommand(command="pbsnodes", stdout='{"nodes": {}}')
    scheduler = PbsClient(ssh_client, "2024.1", timeout=10)
    async with slow_command(ssh_client, pbsnodes):
        with pytest.raises(TimeoutLimitExceeded):
            await scheduler.get_nodes("test", "token")
        await scheduler.get_nodes("test", "token", timeout=OVERRIDE_TIMEOUT)


def cluster_config(probe_timeout: int, connection_mode: str = "ssh"):
    return {
        "name": "cluster",
        "ssh": {"host": "localhost", "port": 22,
                "timeout": {"idle_timeout": 60, "process_setup": 5}},
        "scheduler": {"type": "slurm", "version": "24.11.0",
                      "connection_mode": connection_mode,
                      "api_url": "http://localhost:6820", "api_version": "0.0.42"},
        "service_account": {"client_id": "id", "secret": "secret"},
        "probing": {"services": {"nodes": {"timeout": probe_timeout}}},
    }


def test_probing_timeout_below_ssh_idle_timeout():
    HPCCluster.model_validate(cluster_config(54))
    with pytest.raises(ValidationError, match="idle_timeout"):
        HPCCluster.model_validate(cluster_config(55))


def test_probing_timeout_not_limited_for_rest_scheduler():
    # in `rest` mode the nodes check doesn't use SSH
    HPCCluster.model_validate(cluster_config(120, connection_mode="rest"))
