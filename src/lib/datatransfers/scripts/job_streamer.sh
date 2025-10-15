#!/bin/bash
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


{{ sbatch_directives }}


echo $(date -u) "Ingress/Outgress File Transfer Job (id:${SLURM_JOB_ID:-${PBS_JOBID:-unknown}})"

python3 -m venv .venv
source .venv/bin/activate
pip install firecrest-streamer {% if pypi_index_url is not none %} --index-url {{pypi_index_url}}  {% endif %}




echo $(date -u) "Starting firecrest streamer in {{operation}} mode..."

streamer server --secret {{secret}} --ip 0.0.0.0 --port-range {{port_range}} --wait-timeout {{wait_timeout}} --inbound-transfer-limit {{inbound_transfer_limit}} {{operation}} --path {{target_path}}



