# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.scheduler_clients.models import JobDescriptionModel
from lib.scheduler_clients.pbs.cli_commands.qstat_command import QstatCommand
from lib.scheduler_clients.pbs.cli_commands.qsub_command import QsubCommand
from lib.scheduler_clients.pbs.cli_commands.rstat_reservations_command import (
    RstatReservationsCommand,
)
from lib.scheduler_clients.pbs.models import PbsReservation


def _qsub(**resources):
    job = JobDescriptionModel(
        current_working_directory="/home/u", environment={}, **resources
    )
    return QsubCommand(job).get_command()


def test_qsub_resource_flags():
    cmd = _qsub(
        nodes=2,
        tasks_per_node=4,
        cpus_per_task=2,
        memory_per_node=2048,
        time_limit=90,
    )
    assert cmd.endswith(
        "-l select=2:ncpus=8:mpiprocs=4:ompthreads=2:mem=2048mb"
        " -l place=scatter -l walltime=01:30:00"
    )


def test_qsub_chunk_without_nodes():
    # PBS needs a chunk count in select; without nodes it is a single chunk
    cmd = _qsub(cpus_per_task=4)
    assert cmd.endswith("-l select=1:ncpus=4:ompthreads=4")
    assert "place=" not in cmd


def test_qsub_nodes_only():
    assert _qsub(nodes=3).endswith("-l select=3 -l place=scatter")


def test_qsub_without_resources():
    assert "-l " not in _qsub()


def test_commands_print_times_in_utc():
    assert QstatCommand(ids=["1"]).get_command().startswith("env TZ=UTC qstat ")
    assert RstatReservationsCommand().get_command().startswith(
        "env TZ=UTC pbs_rstat "
    )


def test_rstat_maintenance_and_node_count():
    stdout = "\n".join(
        [
            "Resv ID: M1.pbs",
            "Reserve_Name = NULL",
            "Reserve_Owner = root@pbs",
            "reserve_state = RESV_CONFIRMED",
            "reserve_start = Thu Jun 19 22:00:00 2025",
            "reserve_end = Thu Jun 19 23:00:00 2025",
            "reserve_duration = 3600",
            "queue = M1",
            "Resource_List.ncpus = 2",
            "Resource_List.nodect = 2",
            "resv_nodes = (n1:ncpus=1)+(n2:ncpus=1)",
            "",
            "Resv ID: R2.pbs",
            "Reserve_Name = course",
            "reserve_start = Fri Jun 20 08:00:00 2025",
            "reserve_end = Fri Jun 20 17:00:00 2025",
            "Resource_List.nodect = 1",
            "resv_nodes = (n3:ncpus=4)",
        ]
    )
    reservations = [
        PbsReservation.model_validate(r)
        for r in RstatReservationsCommand().parse_output(stdout, "", 0)
    ]
    assert reservations[0].maintenance is True
    assert reservations[0].node_count == 2
    assert reservations[1].name == "course"
    assert reservations[1].maintenance is False
    assert reservations[1].node_count == 1
