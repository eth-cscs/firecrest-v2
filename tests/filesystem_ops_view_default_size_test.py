# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import pytest

from firecrest.plugins import settings
from tests.mock_ssh_client import MockedCommand


@pytest.fixture
def small_ops_limit():
    """Temporarily lower max_ops_file_size on the test cluster to 1 MiB."""
    cluster = next(c for c in settings.clusters if c.name == "cluster-slurm-ssh")
    original = cluster.data_operation.max_ops_file_size
    cluster.data_operation.max_ops_file_size = 1 * 1024 * 1024
    yield cluster
    cluster.data_operation.max_ops_file_size = original


async def test_view_without_size_is_capped_by_max_ops_file_size(
    client, ssh_client, small_ops_limit
):
    # Default size (5 MiB) must be capped to max_ops_file_size (1 MiB), not rejected.
    command = MockedCommand(
        stdout="ABCDEFGHIJ",
        stderr="",
        exit_code=0,
        command="dd if='/home/readme.txt' bs=1048576 skip=0 count=2",
    )
    async with ssh_client.mocked_output([command]):
        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/view?path=/home/readme.txt"
        )
        assert response.status_code == 200, response.text
        assert response.json()["output"] == "ABCDEFGHIJ"


async def test_view_with_explicit_size_above_limit_is_rejected(
    client, ssh_client, small_ops_limit
):
    async with ssh_client.mocked_output([]):
        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/view?path=/home/readme.txt&size={}".format(
                2 * 1024 * 1024
            )
        )
        assert response.status_code == 400
        assert "must be less than 1048576 bytes" in response.json()["message"]
