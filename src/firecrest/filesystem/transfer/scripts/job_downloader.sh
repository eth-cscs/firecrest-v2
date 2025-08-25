#!/bin/bash
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause


{{ sbatch_directives }}

echo $(date -u) "Ingress File Transfer Job (id:${SLURM_JOB_ID:-${PBS_JOBID:-unknown}})"
echo $(date -u) "Waiting till file to tranfer is available..."
for i in `seq 1440`
do
    status=$(curl --silent --head -o /dev/null --silent -Iw '%{http_code}' "{{ download_head_url | safe }}")
    if [[ "$status" == '200' ]]
        then
            echo $(date -u) "File to transfer found in S3 bucket"
            echo $(date -u) "Downloading file to: {{ target_path }} ..."

            range_length={{ max_part_size }}
            target_file="{{ target_path }}"

            download_complete="false"
            downloaded_data_count=0
            range_from=0
            part_i=1
            headers_file=$(mktemp)

            if [[ -e "$target_file" ]]; then rm "$target_file"; fi

            while [[ "$download_complete" != "true" ]];
            do
                part_file="$target_file.$part_i"
                range_to=$(( range_from + range_length - 1 ))

                http_code=$(curl --compressed --silent -D "$headers_file" --output "$part_file" --range "$range_from-$range_to" -w "%{http_code}" "{{ download_url | safe }}")
                content_range=$(grep -i "Content-Range" "$headers_file")
                file_length=$(echo ${content_range##*/} | tr -cd '[:digit:]')
                content_length=$(grep -i "Content-Length" "$headers_file")
                data_length=$(echo ${content_length##*:} | tr -cd '[:digit:]')

                if [[ "$http_code" == "200" || "$http_code" == "206" ]]; then
                    downloaded_data_count=$(( downloaded_data_count + data_length ))
                    remaining=$(( file_length - downloaded_data_count ))
                    if [[ "$remaining" -le "0" ]]; then download_complete="true" ; fi
                    # enqueue file, remove part
                    cat "$part_file" >> "$target_file"
                    rm "$part_file"
                else
                    echo $(date -u) "Download failed: part $part_i" >&2
                    rm "$headers_file"
                    exit 1
                fi
                range_from=$(( range_to + 1 ))
                part_i=$(( part_i + 1 ))
            done
            echo $(date -u) "Received $downloaded_data_count bytes"
            rm "$headers_file"

            # Convert to MB to make logs more readable
            download_bytes=$(echo | awk -v download_bytes="$downloaded_data_count" ' { printf "%0.3f\n", (download_bytes/1024/1024); } ')
            if [ $? -eq 0 ]
                then
                    echo $(date -u) "File was successfully downloaded (size: ${download_bytes}MB)"
                else
                    echo $(date -u) "Unable to download file" >&2
                    exit 2
                fi
            break
        fi
    sleep 60;
done
