# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import logging

from firecrest.config import get_settings
from tests.helpers import mocked_ssh_sacct_output, mocked_ssh_squeue_output
from tests.mock_ssh_client import MockedCommand


async def test_backend_log_accumulates_every_command_in_a_request(
    client,
    ssh_client,
    slurm_cluster_with_ssh_config,
    caplog,
):
    # GET /jobs/{job_id} issues two SSH commands (sacct then squeue) to serve
    # a single request. Each should be recorded, not just the last one.
    settings = get_settings()
    previously_enabled = settings.logger.enable_tracing_log
    settings.logger.enable_tracing_log = True
    try:
        with caplog.at_level(logging.INFO, logger="f7t_v2_tracing_log"):
            async with ssh_client.mocked_output(
                [
                    MockedCommand(**mocked_ssh_sacct_output()),
                    MockedCommand(**mocked_ssh_squeue_output()),
                ]
            ):
                response = client.get(
                    "/compute/{cluster_name}/jobs/1".format(
                        cluster_name=slurm_cluster_with_ssh_config.name
                    )
                )
                assert response.status_code == 200
    finally:
        settings.logger.enable_tracing_log = previously_enabled

    response_logs = [
        record.msg
        for record in caplog.records
        if record.name == "f7t_v2_tracing_log"
        and record.msg.get("message", "").startswith("Responding")
    ]
    assert len(response_logs) == 1

    backend_log = response_logs[0]["backend"]
    assert len(backend_log) == 2
    assert all(entry["exit_status"] == "0" for entry in backend_log)

    commands = [entry["command"] for entry in backend_log]
    assert any("sacct" in command for command in commands)
    assert any("squeue" in command for command in commands)
