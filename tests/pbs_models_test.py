# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import copy
import json
from importlib import resources as impresources

import pytest

from tests import mocked_ssh_outputs
from lib.scheduler_clients.pbs.cli_commands.pbsnodes_command import PbsnodesCommand
from lib.scheduler_clients.pbs.cli_commands.qstat_command import QstatCommand
from lib.scheduler_clients.pbs.models import (
    PbsJob,
    PbsNode,
    parse_size,
    parse_timestamp,
)


def _load(name):
    output_file = impresources.files(mocked_ssh_outputs) / name
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def qstat_job():
    stdout = _load("ssh_qstat_command.json")["stdout"]
    return QstatCommand(allusers=True).parse_output(stdout, "", 0)[0]


@pytest.fixture(scope="module")
def pbs_node():
    stdout = _load("ssh_pbsnodes_command.json")["stdout"]
    return PbsnodesCommand().parse_output(stdout, "", 0)[0]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1024", 1024),
        ("5660kb", 5660 * 1024),
        ("2048mb", 2048 * 1024**2),
        ("16GB", 16 * 1024**3),
        ("3w", 24),
        ("1.5gb", None),
        (None, None),
        (42, 42),
    ],
)
def test_parse_size(value, expected):
    assert parse_size(value) == expected


def test_parse_timestamp_is_utc():
    # qstat and pbs_rstat run with TZ=UTC, whatever the local zones are
    assert parse_timestamp("Thu Jun 19 21:27:51 2025") == 1750368471
    assert parse_timestamp(1750368471) == 1750368471


def test_job_resources(qstat_job):
    job = PbsJob.model_validate(qstat_job)
    assert job.time.submission == 1750368471
    assert job.time.start == 1750368471
    assert job.time.total_cpu == 0
    assert job.allocation_cpus == 1
    assert job.max_rss == 5660 * 1024
    # not requested or not configured on this server
    assert job.requested_memory is None
    assert job.allocation_gpus is None
    assert job.consumed_energy is None


def test_job_memory_gpus_and_energy(qstat_job):
    raw = copy.deepcopy(qstat_job)
    raw["Resource_List"].update({"mem": "4gb", "ngpus": 2})
    raw["resources_used"].update(
        {"cput": "01:02:03", "mem": "2048mb", "energy": 0.5}
    )
    job = PbsJob.model_validate(raw)
    assert job.time.total_cpu == 3723
    assert job.requested_memory == 4096
    assert job.max_rss == 2048 * 1024**2
    assert job.allocation_gpus == 2
    # 0.5 kWh
    assert job.consumed_energy == 1_800_000


def test_node_memory_in_mib(pbs_node):
    # resources_available.mem = "1024mb", the same unit Slurm reports
    assert PbsNode.model_validate(pbs_node).free_memory == 1024
    raw = {**pbs_node, "resources_assigned": {"mem": "2gb", "ncpus": 1}}
    assert PbsNode.model_validate(raw).alloc_memory == 2048


def test_node_reason(pbs_node):
    assert PbsNode.model_validate(pbs_node).reason is None
    raw = {**pbs_node, "state": "offline", "comment": "Bad DIMM"}
    assert PbsNode.model_validate(raw).reason == "Bad DIMM"
