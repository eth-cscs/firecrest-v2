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
# Utilities
#
# Cleanup
cleanup() {
    echo "Cleanup"
    if [ -d "$PARTS_DIR" ]; then
        rm -fr "$PARTS_DIR" 
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
# Configuration
PARTS_DIR="parts"           # Local directory to store parts
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
  \"transferDirectives\": {
      \"fileSize\":\"${UPLOAD_FILE_SIZE}\",
      \"transferMethod\":\"s3\"
  }
}")

# Extract information
parts_upload_urls=$(echo $response | jq -r ".partsUploadUrls")
complete_upload_url=$(echo $response | jq -r ".completeUploadUrl")
max_part_size=$(echo $response | jq -r ".maxPartSize")

# Prepare parts
echo "Split file"
mkdir -p "$PARTS_DIR"
cd "$PARTS_DIR"
split "../$DATA_FILE" -b "$max_part_size" --numeric-suffixes=1 --suffix-length=5
cd - > /dev/null

# Upload parts and get Etags
part_id=1
upload_error=false
etags_xml=""
while read -r part_url; do
    part_file=$(printf "%s/x%05d" $PARTS_DIR ${part_id})
    echo "Uploading part ${part_id}: ${part_file}"
    # Upload data with curl and extract ETag
    if line=$(curl -f --show-error -D - --upload-file "$part_file" "$part_url" | grep -i "^ETag: " ) ;
    then
        etag=$(echo $line | awk -F'"' '{print $2}')
        etags_xml="${etags_xml}<Part><PartNumber>${part_id}</PartNumber><ETag>\"${etag%|*}\"</ETag></Part>"
    else
        >&2 echo "Error uploading part ${part_id}"
        upload_error=true
    fi
    # Increase part index
    part_id=$(( part_id + 1 ))
done <<< "$(echo "$parts_upload_urls" | jq -r '.[]')"

if $upload_error; 
then
    >&2 echo "Upload failed."
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
