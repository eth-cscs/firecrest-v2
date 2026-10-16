# Copyright (c) 2026, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.scheduler_clients.slurm.cli_commands.sacct_base import SLURM_FIELD_DELIMITER
from lib.scheduler_clients.slurm.cli_commands.sacct_job_info_command import SacctCommand
from lib.scheduler_clients.slurm.cli_commands.sacct_job_metadata_command import (
    SacctJobMetadataCommand,
)


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
