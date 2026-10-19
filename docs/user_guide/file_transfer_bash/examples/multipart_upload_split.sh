#!/bin/bash
set -euo pipefail
# -----------------------------------------------------------------------------
# Arguments
if [ "$#" -lt "4" ];
then
    echo "usage: $0 <data_file> <system> <destination> <env_file> [<scheduler_account>]"
    exit 1
fi
DATA_FILE="$1"
F7T_SYSTEM="$2"
DESTINATION_PATH="$3"
ENV_FILE="$4"
SCHEDULER_ACCOUNT=${5:-staff}
if [ ! -f "$DATA_FILE" ]; then 
    echo "$DATA_FILE not found"
    exit 1
fi
if [ ! -f "$ENV_FILE"  ]; then 
    echo "$ENV_FILE not found"
    exit 2
fi


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
# Load environment
source "$ENV_FILE"

# -----------------------------------------------------------------------------
# MAIN
echo "Upload file: $DATA_FILE"
# Get file size (in bytes)
UPLOAD_FILE_SIZE="$(stat --printf "%s" "$DATA_FILE")"

# Get Access Token
# Current token not provided or expired, get a new one
response="$(curl -s --request POST \
--url "$TOKEN_URI" \
--header "content-type: application/x-www-form-urlencoded" \
--data "grant_type=client_credentials" \
--data "client_id=$CLIENT_ID" \
--data "client_secret=$CLIENT_SECRET")"

# Get the JWT token
ACCESS_TOKEN="$(echo "$response" | jq -r '.access_token')"
if [ -z "$ACCESS_TOKEN" ] || [ "$ACCESS_TOKEN" = "null" ]; then
  echo "Error: failed to obtain access token. Response: $response" >&2
  exit 3
fi

# Submit upload file request to FirecREST
raw_response=$(curl -s -w "\n%{http_code}" --location --globoff "${F7T_URL}/filesystem/${F7T_SYSTEM}/transfer/upload" \
--header "Content-Type: application/json" \
--header "Authorization: Bearer $ACCESS_TOKEN" \
--data "{
  \"path\":\"${DESTINATION_PATH}\",
  \"fileName\":\"${DATA_FILE}\",
  \"account\":\"${SCHEDULER_ACCOUNT}\",
  \"transferDirectives\": {
      \"fileSize\":\"${UPLOAD_FILE_SIZE}\",
      \"transferMethod\":\"s3\"
  }
}")

# Split body and HTTP status code (last line)
http_status="${raw_response##*$'\n'}"
response="${raw_response%$'\n'*}"
if [[ ! "$http_status" =~ ^2[0-9]{2}$ ]]; then
    >&2 echo "Upload request failed with HTTP status: $http_status. Response: $response"
    exit 4
fi

# Error check
if [[ "$(echo "$response" | jq -r '.errorType')" == "error" ]]; then
    echo "RESPONSE ERROR: $(echo "$response" | jq -r '.message')"
    exit 4
fi

# Extract information
directives="$(echo "$response" | jq -r ".transferDirectives")"
parts_upload_urls="$(echo "$directives" | jq -r ".partsUploadUrls")"
complete_upload_url="$(echo "$directives" | jq -r ".completeUploadUrl")"
# Max part size shall be expressed in MB
max_part_size="$(echo $directives | jq -r ".maxPartSize")"

# Prepare parts
echo "Split file"
PARTS_DIR="$(mktemp -d -p .)"
split "$DATA_FILE" -b "$max_part_size" --numeric-suffixes=1 --suffix-length=5 "${PARTS_DIR}/x"

# Upload parts and get Etags
part_id=1
upload_error=false
etags_xml=""
while read -r part_url; do
    part_file=$(printf "%s/x%05d" "$PARTS_DIR" "${part_id}")
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
