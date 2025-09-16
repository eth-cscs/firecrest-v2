#!/bin/bash
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


{{ sbatch_directives }}


echo $(date -u) "Ingress File Transfer Job (id:${SLURM_JOB_ID:-${PBS_JOBID:-unknown}})"

python3 -m venv .venv
source .venv/bin/activate
pip install magic-wormhole --index-url {{pypi_index_url}}

echo $(date -u) "Waiting till file to tranfer is available..."

wormhole send {{source}} --code {{wormhole_code}}