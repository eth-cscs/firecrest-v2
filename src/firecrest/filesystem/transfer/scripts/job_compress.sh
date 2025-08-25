#!/bin/bash
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


{{ sbatch_directives }}

echo $(date -u) "Compress Files Job (id:${SLURM_JOB_ID:-${PBS_JOBID:-unknown}})"

{% if match_pattern %}

status=$(cd {{ source_dir }}; find . -type f -regex '{{ match_pattern }}' -print0 | tar {{ options }} -czvf '{{ target_path }}' --null --files-from - )
if [[ "$?" == '0' ]]
then
    echo $(date -u) "Files were successfully compressed."
    echo -e "Files compressed:\n$status"
    exit 0
else
    echo $(date -u) "Unable to compress files exit code:${?} error: ${status}" >&2
    exit $?
fi

{% else %}

status=$(tar {{ options }} -czvf '{{ target_path }}' -C '{{ source_dir }}'  '{{ source_file }}')
if [[ "$?" == '0' ]]
then
    echo $(date -u) "Files were successfully compressed."
    exit 0
else
    echo $(date -u) "Unable to compress files exit code:${?} error: ${status}" >&2
    exit $?
fi

{% endif %}