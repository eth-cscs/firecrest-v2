#!/bin/bash
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


{{ sbatch_directives }}


echo $(date -u) "Ingress/Outgress File Transfer Job (id:${SLURM_JOB_ID:-${PBS_JOBID:-unknown}})"

python3.11 -m venv .venv
source .venv/bin/activate
pip install streamer --index-url {{pypi_index_url}}

echo $(date -u) "Waiting till file to tranfer is available..."

streamer {{operation}} {{streamer_coordinates}} --path {{target_path}}