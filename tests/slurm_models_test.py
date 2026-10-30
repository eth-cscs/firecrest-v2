# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import copy
import json
from importlib import resources as impresources

import pytest

from tests import mocked_api_responses
from lib.scheduler_clients.slurm.models import (
    SlurmJob,
    SlurmNode,
    SlurmReservations,
)


def _load(name):
    response_file = impresources.files(mocked_api_responses) / name
    with response_file.open("r") as response:
        return json.load(response)


@pytest.fixture(scope="module")
def db_job():
    return _load("slurm_get_job_from_db.json")["jobs"][0]


@pytest.fixture(scope="module")
def ctl_job():
    return _load("slurm_get_job.json")["jobs"][0]


def _tres(tres_type, count, name=""):
    return {"type": tres_type, "name": name, "id": 1, "count": count}


def _step(max_tres=()):
    return {
        "step": {"id": "1.batch", "name": "batch"},
        "state": "COMPLETED",
        "exit_code": {"status": ["SUCCESS"], "return_code": {"number": 0}},
        "time": {"elapsed": 1, "start": {"number": 1}, "end": {"number": 2}},
        "tres": {
            "requested": {
                "max": list(max_tres),
                "min": [],
                "average": [],
                "total": [],
            }
        },
    }


def test_accounting_job_resources(db_job):
    job = SlurmJob.model_validate(db_job)
    assert job.time.submission == 1710516603
    assert job.time.total_cpu == 0
    assert job.allocation_cpus == 1
    assert job.requested_memory == 1000
    # energy TRES is null where no acct_gather_energy plugin is configured
    assert job.consumed_energy is None
    assert job.allocation_gpus is None


def test_accounting_job_gpus_and_max_rss(db_job):
    raw = copy.deepcopy(db_job)
    raw["time"]["total"] = {"seconds": 635, "microseconds": 0}
    raw["tres"]["allocated"] += [
        _tres("gres", 4, "gpu"),
        _tres("gres", 2, "gpumem"),
    ]
    raw["tres"]["allocated"][2]["count"] = 2000  # energy
    raw["steps"] = [
        _step(max_tres=[_tres("mem", 4263433216)]),
        _step(max_tres=[_tres("mem", 5201004544), _tres("gres", 1024, "gpumem")]),
    ]
    job = SlurmJob.model_validate(raw)
    assert job.time.total_cpu == 635
    # gres/gpumem on the job is not a GPU count
    assert job.allocation_gpus == 4
    assert job.consumed_energy == 2000
    assert job.max_rss == 5201004544


def test_accounting_job_without_step_usage(db_job):
    raw = copy.deepcopy(db_job)
    raw["steps"] = [_step()]
    job = SlurmJob.model_validate(raw)
    assert job.max_rss is None


def test_controller_job_resources(ctl_job):
    raw = copy.deepcopy(ctl_job)
    raw["cpus"] = {"set": True, "infinite": False, "number": 8}
    raw["memory_per_node"] = {"set": True, "infinite": False, "number": 2048}
    raw["node_count"] = {"set": True, "infinite": False, "number": 2}
    job = SlurmJob.model_validate(raw)
    assert job.time.submission == 1773058655
    assert job.allocation_cpus == 8
    assert job.requested_memory == 4096


def test_controller_job_unset_memory(ctl_job):
    # memory_per_node is 0 when the job asked for --mem-per-cpu or nothing
    job = SlurmJob.model_validate(ctl_job)
    assert job.requested_memory is None
    assert job.allocation_cpus == 1


def test_node_slurmrestd_fields():
    node = SlurmNode.model_validate(
        {
            "name": "node010",
            "hostname": "node010",
            "address": "node010",
            "state": ["IDLE", "DRAIN"],
            "sockets": 2,
            "cores": 32,
            "threads": 1,
            "cpus": 64,
            "alloc_cpus": 0,
            "alloc_idle_cpus": 64,
            "alloc_memory": 0,
            "real_memory": 524288,
            "free_mem": {"set": True, "infinite": False, "number": 521216},
            "cpu_load": {"set": True, "infinite": False, "number": 18},
            "partitions": "debug,compute",
            "features": [],
            "weight": 1,
            "reason": "Bad DIMM",
        }
    )
    assert node.free_memory == 521216
    assert node.idle_cpus == 64
    assert node.cpu_load == 18
    assert node.partitions == ["debug", "compute"]
    assert node.reason == "Bad DIMM"


def test_reservation_fields():
    reservation = SlurmReservations.model_validate(
        {
            "name": "maint",
            "node_list": "node[002-003]",
            "nodes": "node[002-003]",
            "start_time": {"set": True, "infinite": False, "number": 1792435054},
            "end_time": {"set": True, "infinite": False, "number": 1792442254},
            "node_count": {"set": True, "infinite": False, "number": 2},
            "flags": ["MAINT", "SPEC_NODES"],
        }
    )
    assert reservation.node_count == 2
    assert reservation.maintenance is True
    # slurmrestd may omit features
    assert reservation.features is None


def test_reservation_not_maintenance():
    reservation = SlurmReservations.model_validate(
        {
            "name": "course",
            "node_list": "node001",
            "start_time": 1792435054,
            "end_time": 1792442254,
            "flags": ["SPEC_NODES"],
        }
    )
    assert reservation.maintenance is False
