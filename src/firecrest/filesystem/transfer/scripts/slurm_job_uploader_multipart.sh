#!/bin/bash -l
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause



{{ sbatch_directives }}

# ----------------------------------------------------------------------------
# GLOBAL CONFIGURATION
BLOCK_SIZE=1048576
MAX_PART_SIZE={{ F7T_MAX_PART_SIZE }}

# Global parts array
parts_url=({{ F7T_MP_PARTS_URL | safe }})

# ----------------------------------------------------------------------------
# UTILITY FUNCTIONS

# Create the standard part file name
# Parameters:
# $1: parts directory
# $2: padding
# $2: part id
function get_part_filename () {
    local part_path=$1
    local padding=$2
    local p=$3
    printf "$part_path/%0${padding}g.part" "$p"
}

# Create the standard file name for result files handling ETag
# Parameters:
# $1: part file
function get_part_result_filename() {
    local part_file=$1
    echo "$part_file.result"
}

# Generate a unique named directory
# Parameters
# $1: tmp_directory
function create_temporary_directory() {
    local tmp_directory=$1
    # Try to create parent directory
    mkdir -p "$tmp_directory"
    # Create temporary directory
    local datestamp
    datestamp=$(date +%Y%m%d_%H%M%S%N)

    mktemp -d "${tmp_directory}/${datestamp}_XXXXXXXXXXXXX"
}

# Upload job
# Parameters
# $1: original input file
# $2: part output file
# $3: part size in blocks
# $4: part id
# $5: part URL
function job_dd() {
    local input_file=$1
    local part_file=$2
    local part_size=$3
    local part_id=$4
    local part_url=$5
    local skip

    # First chunk does not have any offset
    if [ "$part_id" -eq 1 ];
    then
        skip=""
    else
        # Offset for each chunk
        skip="skip=$((( part_id - 1 ) * part_size))"
    fi

    # Generate part file
    if ! dd if="$input_file" of="$part_file" bs=$BLOCK_SIZE count="$part_size" $skip status=none ; then
        local error_code=$?
        >&2 echo "error_generating_part_file $error_code"
        exit $error_code
    fi

    # Upload part file
    job_upload "$part_file" "$part_id" "$part_url"
}

# Upload job
# Parameters
# $1: part file
# $2: part id
# $3: part URL
function job_upload() {
    local part_file=$1
    local part_id=$2
    local part_url=$3
    local data
    
    echo "[INFO] Uploading part $part_id..."

    # Upload data with curl and extract ETag
    if ! data=$(curl -s -D - --upload-file "$part_file" "$part_url" | grep "ETag");
    then
        # Non-blocking error notification
        # (.result file not generated and evaluated later, part file still in transfer directory)
        >&2 echo "error_curl part $part_id"
    else
        # Create .result file and remove uploaded part file
        echo "$data" > "$(get_part_result_filename "$part_file")"
        rm "$part_file"
    fi
}

# Upload control loop
# Execute concurrent upload based on the selection (with or without generation of part files).
# Parameters:
# $1: input file
# $2: number of parts
# $3: part files were already generated
# $4: path of parts' directory
# $5: padding for part's file name
# $6: number of parallel uploads
# $7: maximum number of blocks (standard 1MB each) for part
function upload_loop() {
    local input_file=$1
    local num_parts=$2
    local part_file_generated=$3
    local part_path=$4
    local padding=$5
    local parallel_run=$6
    local blocks_per_part=$7 # requested only if part_file_generated == false
    local p
    local i
    local part_url

    p=1
    while [[ $p -le $num_parts ]]
    do
        i=0
        while [[ $i -lt $parallel_run && $p -le $num_parts ]]
        do
            # Unique name for temporary part
            part_file=$(get_part_filename "$part_path" "$padding" $p)
            part_url="${parts_url[$(( p - 1 ))]}"
            if [ "$part_file_generated" = false ];
            then
                # Generate part file and upload
                job_dd "$input_file" "$part_file" "$blocks_per_part" $p "$part_url" &
            else
                # Process upload only if part file exists
                if [ -f "$part_file" ];
                then
                    # Launch upload job for existing parts
                    job_upload "$part_file" $p "$part_url" &
                fi
            fi
            # Next part
            ((i++))
            ((p++))
        done
        # Sync concurrent running upload background jobs
        wait
    done
}

# ----------------------------------------------------------------------- #
## MAIN
## Default values for arguments
tmp_directory="{{ F7T_TMP_FOLDER }}"
parallel_run={{ F7T_MP_PARALLEL_RUN }}
use_split={{ F7T_MP_USE_SPLIT }}
num_parts={{ F7T_MP_NUM_PARTS }}
input_file={{ F7T_MP_INPUT_FILE }}
complete_multipart_url='{{ F7T_MP_COMPLETE_URL | safe }}'

echo "[INFO] Uploading file:$input_file into $num_parts chunks"

# Check input file
if [ ! -f "$input_file" ];
then
    >&2 echo "file_not_found"
    # Return error code ENOENT
    exit 34
fi

# Define padding for part files naming
tmp=$(printf "%d" "$num_parts")
[ "$num_parts" -lt 10 ] && padding="2" || padding=$(expr length $tmp)

echo "[INFO] Creating temporary folder:$tmp_directory"

# Create temporary directory for part files
if ! part_path=$(create_temporary_directory "$tmp_directory") ;
then
    >&2 echo "cannot create temporary directory"
    # Return error code ENOENT
    exit 34
fi

if [ "$use_split" = true ];
then
    echo "[INFO] Splitting file: $input_file in parts $part_path/${input_file}_"
    # Split file in parts
    split -n "$num_parts" --numeric=1 --additional-suffix=.part "$input_file" "$part_path/${input_file}_"
else
    # File is split while uploading
    # Check part size
    file_size=$(stat -c %s "$input_file")
    # ceiling division
    # https://stackoverflow.com/questions/2394988/get-ceiling-integer-from-number-in-linux-bash
    part_size=$(( (file_size + num_parts - 1) / num_parts ))
    blocks_per_part=$(( (part_size + BLOCK_SIZE - 1) / BLOCK_SIZE ))
    if [ $part_size -gt $MAX_PART_SIZE ]; then
        >&2 echo "error_max_part_size"
        # Return error code EFBIG
        exit 27
    fi
fi

# Upload loop
upload_loop "$input_file" "$num_parts" "$use_split" "$part_path" "$padding" "$parallel_run" "$blocks_per_part"
# Retry with not uploaded .part files
upload_loop "$input_file" "$num_parts" true         "$part_path" "$padding" "$parallel_run"

echo "[INFO] Parts upload completed."

# Verify and collect ETag
error=false
etagsXML=""
for p in $(seq 1 $num_parts)
do
    echo -n "[INFO] Upload of part ${p} "
    result_file=$(get_part_result_filename $(get_part_filename $part_path $padding $p))
    if [[ -f $result_file ]];
    then
        # Result file exists: get contents in single line, labeling it with part ID
        line=$(cat "$result_file" | tr -d "\"" | tr -d "\n" | tr "\r" "|")
        echo "succeded with $line"
        etag=${line#*: }
        etagsXML="${etagsXML}<Part><PartNumber>${p}</PartNumber><ETag>\"${etag%|*}\"</ETag></Part>"
    else
        # Result file does not exist for the part $p. Mark error and proceed with next one.
        echo "failed"
        >&2 echo -n "upload_failed_part_$p"
        error=true
    fi
done

echo "[INFO] Signaling multipart upload completion"

completeUploadXML="<CompleteMultipartUpload xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\">${etagsXML}</CompleteMultipartUpload>"

# Complete multipart upload
status=$(curl -f --show-error -s -i -o /dev/null -w "%{http_code}" -d "$completeUploadXML" -X POST $complete_multipart_url)

if [[ "$status" == '200' ]]
then
    echo "[INFO] Multipart file upload successfully completed"
    # Cleanup
    rm -fr "$part_path"
    rmdir "$tmp_directory" 2>/dev/null
    # Return Success
    exit 0
else
    # Return Communication Error on Send (ECOMM)
    exit 70
fi