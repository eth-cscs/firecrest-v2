#!/bin/bash
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


{{ sbatch_directives }}


echo $(date -u) "Ingress/Outgress File Transfer Job (id:${SLURM_JOB_ID:-${PBS_JOBID:-unknown}})"

latest_python=$(compgen -c python | grep -E '^python[0-9.]+$' | sort -V | tail -1)
echo "Most recent Python version detected is: $latest_python"

$latest_python -m venv .venv
source .venv/bin/activate
cd /app/firecrest-streamer
pip install -r requirements.txt
cd src
echo $(date -u) "Starting firecrest streamer in {{operation}} mode..."

python -m streamer server --secret {{secret}} --host {{host}} {% for ip in public_ips %} --public-ips {{ip}} {% endfor %} --port-range {{port_range}} --wait-timeout {{wait_timeout}} --inbound-transfer-limit {{inbound_transfer_limit}} {{operation}} --path {{target_path}}
