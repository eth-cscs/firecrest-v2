#!/bin/bash
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


{{ sbatch_directives }}

echo $(date -u) "Copy Files Job (id:${SLURM_JOB_ID})"


if [ "{{ dereference }}" = "True" ]; then 
    derefparam="L"
else
    derefparam="d"
fi

status=$(cp --force -R${derefparam} --preserve=all -- '{{ source_path }}' '{{ target_path }}')


if [[ "$?" == '0' ]]
then
    echo $(date -u) "Files were successfully copied."
    exit 0
else
    echo $(date -u) "Unable to copy files exit code:${?} error: ${status}" >&2
    exit $?
fi

