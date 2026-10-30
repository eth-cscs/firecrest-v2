# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.scheduler_clients.models import JobDescriptionModel
from lib.scheduler_clients.slurm.cli_commands.sacct_base import SLURM_FIELD_DELIMITER
from lib.scheduler_clients.slurm.cli_commands.sacct_job_info_command import SacctCommand
from lib.scheduler_clients.slurm.cli_commands.sacct_job_metadata_command import (
    SacctJobMetadataCommand,
)
from lib.scheduler_clients.slurm.cli_commands.sbatch_command import SbatchCommand
from lib.scheduler_clients.slurm.cli_commands.sinfo_command import SinfoCommand
from lib.scheduler_clients.slurm.models import SlurmNode
from lib.scheduler_clients.models import NodeState


def _line(*fields):
    return SLURM_FIELD_DELIMITER.join(fields)


def test_sacct_job_name_with_pipe():
    # Job names may contain "|", which used to break field splitting
    stdout = "\n".join(
        [
            _line(
                "8167067", "1", "eiger", "0:0", "users", "u8", "45/20/1A|I1|R1-12",
                "nid001", "normal", "1", "RUNNING", "None", "61", "1787127431",
                "1787127431", "Unknown", "00:00:00", "60", "vcardena",
                "/scratch/vcardena/45-CHL20-13F",
            ),
            _line(
                "8167067.batch", "1", "eiger", "", "", "u8", "batch", "nid001",
                "", "", "RUNNING", "", "61", "1787127431", "1787127431",
                "Unknown", "00:00:00", "", "", "",
            ),
        ]
    )
    jobs = SacctCommand().parse_output(stdout, "", 0)
    assert len(jobs) == 1
    assert jobs[0]["jobId"] == "8167067"
    assert jobs[0]["name"] == "45/20/1A|I1|R1-12"
    assert jobs[0]["workingDirectory"] == "/scratch/vcardena/45-CHL20-13F"
    assert jobs[0]["steps"][0]["step"]["id"] == "8167067.batch"


def test_sacct_orphan_step_is_skipped():
    stdout = _line(
        "8167067.batch", "1", "eiger", "", "", "u8", "batch", "nid001", "", "",
        "RUNNING", "", "61", "1787127431", "1787127431", "Unknown", "00:00:00",
        "", "", "",
    )
    assert SacctCommand().parse_output(stdout, "", 0) is None


def test_sacct_metadata_job_name_with_pipe():
    stdout = _line("8167067", "a|b", "", "slurm-%j.out", "", "/scratch/u")
    jobs = SacctJobMetadataCommand().parse_output(stdout, "", 0)
    assert jobs[0]["jobName"] == "a|b"
    assert jobs[0]["standardOutput"] == "/scratch/u/slurm-8167067.out"


def test_sinfo_multi_state_is_split():
    stdout = (
        "2:1:1|2|3.53|2097|f7t|nid001|nid001|nid001|MIXED+PLANNED|normal|1|"
        "24.05.4|1000|1/1/0/2\n"
        "2:1:1|2|3.53|2097|f7t|nid002|nid002|nid002|IDLE+DRAIN*|normal|1|"
        "24.05.4|1000|0/2/0/2"
    )
    nodes = list(SinfoCommand().parse_output(stdout, ""))

    assert nodes[0]["state"] == ["MIXED", "PLANNED"]
    assert nodes[1]["state"] == ["IDLE", "DRAIN*"]
    assert SlurmNode(**nodes[0]).state == [NodeState.MIXED, NodeState.PLANNED]
    assert SlurmNode(**nodes[1]).state == [NodeState.IDLE, NodeState.DRAIN]


def _sbatch(**resources):
    job = JobDescriptionModel(
        current_working_directory="/home/u", environment={}, **resources
    )
    return SbatchCommand(job).get_command()


def test_sbatch_resource_flags():
    cmd = _sbatch(
        nodes=4,
        tasks_per_node=4,
        cpus_per_task=2,
        memory_per_node=2048,
        time_limit=90,
    )
    assert cmd.endswith(
        "--nodes=4 --ntasks-per-node=4 --cpus-per-task=2 --mem=2048 --time=90"
    )


def test_sbatch_without_resources():
    cmd = _sbatch()
    for flag in ("--nodes", "--ntasks-per-node", "--cpus-per-task", "--mem", "--time"):
        assert flag not in cmd
