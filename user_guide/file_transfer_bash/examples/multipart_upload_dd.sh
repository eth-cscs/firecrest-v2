#!/bin/bash
set -E
# -----------------------------------------------------------------------------
# Arguments
if [ "$#" -ne "4" ];
then
    echo "usage: $0 <data_file> <system> <destination> <env_file>"
    exit 1
fi
DATA_FILE="$1"
F7T_SYSTEM="$2"
DESTINATION_PATH="$3"
ENV_FILE="$4"
if [ ! -f "$DATA_FILE" ]; then echo "$DATA_FILE not found"; fi
if [ ! -f "$ENV_FILE"  ]; then echo "$ENV_FILE not found";  fi

# -----------------------------------------------------------------------------
# Configuration
PART_FILE="${DATA_FILE}.part" # Temporary file to store parts
BLOCK_SIZE=1048576  # 1MB

# -----------------------------------------------------------------------------
# Utilities
#
# Cleanup
cleanup() {
    echo "Cleanup"
    if [ -d "$PART_FILE" ]; then
        rm -fr "$PART_FILE" 
    fi
}
#
# Error handler
error_handler() {
    >&2 echo "error $@ on line $1"
    cleanup
    exit 99
}
trap 'error_handler $LINENO' ERR

# -----------------------------------------------------------------------------
# Load environment
source "$ENV_FILE"

# -----------------------------------------------------------------------------
# MAIN
echo "Upload file: $DATA_FILE"
# Get file size (in bytes)
UPLOAD_FILE_SIZE=$(stat --printf "%s" "$DATA_FILE")

# Get Access Token
# Current token not provided or expired, get a new one
response=$(curl -s --request POST \
--url "$TOKEN_URI" \
--header "content-type: application/x-www-form-urlencoded" \
--data "grant_type=client_credentials" \
--data "client_id=$CLIENT_ID" \
--data "client_secret=$CLIENT_SECRET")
# Get the JWT token
ACCESS_TOKEN=$(echo $response | jq -r '.access_token')

# Submit upload file request to FirecREST
response=$(curl -s --location --globoff "${F7T_URL}/filesystem/${F7T_SYSTEM}/transfer/upload" \
--header "Content-Type: application/json" \
--header "Authorization: Bearer $ACCESS_TOKEN" \
--data "{
  \"path\":\"${DESTINATION_PATH}\",
  \"fileName\":\"${DATA_FILE}\",
  \"fileSize\":\"${UPLOAD_FILE_SIZE}\"
}")

# Extract information
parts_upload_urls=$(echo $response | jq -r ".partsUploadUrls")
complete_upload_url=$(echo $response | jq -r ".completeUploadUrl")
max_part_size=$(echo $response | jq -r ".maxPartSize")


# Upload parts and get Etags
part_id=1
upload_error=false
etags_xml=""
skip=""
# Define the part size, depending on the block size
part_blocks=$(( max_part_size / BLOCK_SIZE ))
while read -r part_url; do    
    # Generate temporary part file    
    if ! dd if="${DATA_FILE}" of="${PART_FILE}" bs=${BLOCK_SIZE} count=${part_blocks} ${skip} status=none ; then
        >&2 echo "Error generating part file for part ${part_id}"
        upload_error=true
    else
        ls -hl
        echo "Uploading part ${part_id}: ${PART_FILE}"
        # Upload data with curl and extract ETag
        if line=$(curl -f --show-error -D - --upload-file "$PART_FILE" "$part_url" | grep -i "^ETag: " ) ;
        then
            etag=$(echo $line | awk -F'"' '{print $2}')
            etags_xml="${etags_xml}<Part><PartNumber>${part_id}</PartNumber><ETag>\"${etag%|*}\"</ETag></Part>"
        else
            >&2 echo "Error uploading part ${part_id}"
            upload_error=true
        fi
        # Cleanup
        rm "${PART_FILE}"
    fi
    # Increase part index
    part_id=$(( part_id + 1 ))
    # Offset for next chunk
    skip="skip=$((( part_id - 1 ) * part_blocks))"

done <<< "$(echo "$parts_upload_urls" | jq -r '.[]')"

if $upload_error; 
then
    >&2 echo "Upload failed."
    cleanup
    exit 2
fi

echo "Completing upload"
complete_upload_xml="<CompleteMultipartUpload xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\">${etags_xml}</CompleteMultipartUpload>"

# Complete multipart upload
status=$(curl -f --show-error -i -o /dev/null -w "%{http_code}" -H "Content-Type: application/xml" -d "$complete_upload_xml" -X POST $complete_upload_url)
if [[ "$status" == "200" ]]
then
    echo "File upload successfully completed"
else
    >&2 echo "File upload failed with status: $status"
    exit 3
fi

cleanup
# -----------------------------------------------------------------------------
