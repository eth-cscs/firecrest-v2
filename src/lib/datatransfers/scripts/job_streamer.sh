#!/bin/bash
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


{{ sbatch_directives }}


echo $(date -u) "Ingress/Outgress File Transfer Job (id:${SLURM_JOB_ID:-${PBS_JOBID:-unknown}})"

latest_python=$(compgen -c python | grep -E '^python[0-9.]+$' | sort -V | tail -1)
echo "Most recent Python version detected is: $latest_python"


if $latest_python -c 'import sys; sys.exit(0 if sys.version_info < (3, 8) else 1)'; then
    echo "Error: python version is too old. Minimum required version is 3.8."
    exit 1
fi

{% if operation == "send" %}  
if [ ! -f "{{target_path}}" ]; then
    echo "Error: source file does not exist."
    exit 1
fi
{% elif operation == "receive" %}
if [ -f "{{target_path}}" ]; then
    echo "Error: destination file already exist."
    exit 1
fi
{% endif %}


export env_folder=".venv-${SLURM_JOB_ID:-${PBS_JOBID:-unknown}}"
cleanup() { 
    echo $(date -u) "Clean up temp env folder...";
    rm -rf $env_folder;
}
trap cleanup EXIT


$latest_python -m venv ${env_folder}
source ${env_folder}/bin/activate
pip install firecrest-streamer {% if pypi_index_url is not none %} --index-url {{pypi_index_url}}  {% endif %}


echo $(date -u) "Starting firecrest streamer in {{operation}} mode..."

streamer server --secret {{secret}} --host {{host}} {% for ip in public_ips %} --public-ips {{ip}} {% endfor %} --port-range {{port_range}} --wait-timeout {{wait_timeout}} --inbound-transfer-limit {{inbound_transfer_limit}} {{operation}} --path {{target_path}}
