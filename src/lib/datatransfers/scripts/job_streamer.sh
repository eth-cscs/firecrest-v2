#!/bin/bash
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


{{ sbatch_directives }}


echo $(date -u) "Ingress/Outgress File Transfer Job (id:${SLURM_JOB_ID:-${PBS_JOBID:-unknown}})"

python3.11 -m venv .venv
source .venv/bin/activate
pip install firecrest-streamer --index-url {{pypi_index_url}}

echo $(date -u) "Starting firecrest streamer in {{operation}} mode..."

streamer server {{operation}} --secret {{secret}} --path {{target_path}}



