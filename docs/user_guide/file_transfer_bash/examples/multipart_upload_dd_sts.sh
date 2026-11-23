#!/bin/bash
set -euo pipefail

# Requires curl with --aws-sigv4, jq, Python 3, and GNU dd.
if [ "$#" -lt 4 ]; then
    echo "usage: $0 <data_file> <system> <destination> <env_file> [<scheduler_account>]" >&2
    exit 1
fi

DATA_FILE="$1"
F7T_SYSTEM="$2"
DESTINATION_PATH="$3"
ENV_FILE="$4"
SCHEDULER_ACCOUNT="${5:-staff}"
if [ ! -f "$DATA_FILE" ]; then
    echo "$DATA_FILE not found" >&2
    exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
    echo "$ENV_FILE not found" >&2
    exit 2
fi

source "$ENV_FILE"
S3_URL="${S3_URL:-http://localhost:9000}"
S3_REGION="${S3_REGION:-us-east-1}"
OBJECT_KEY="${S3_OBJECT_KEY:-$(basename -- "$DATA_FILE")}"
UPLOAD_FILE_SIZE="$(stat --printf '%s' "$DATA_FILE")"
if [ "$UPLOAD_FILE_SIZE" -eq 0 ]; then
    echo "Cannot multipart upload an empty file" >&2
    exit 1
fi

response="$(curl -fsS --request POST \
    --url "$TOKEN_URI" \
    --header "content-type: application/x-www-form-urlencoded" \
    --data "grant_type=client_credentials" \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode "client_secret=$CLIENT_SECRET")"
if ! ACCESS_TOKEN="$(jq -er '.access_token | strings | select(length > 0)' <<< "$response")"; then
    echo "Token response did not contain an access token" >&2
    exit 1
fi

if [ -z "${BUCKET:-}" ]; then
    payload="$(cut -d. -f2 <<< "$ACCESS_TOKEN" | tr '_-' '/+')"
    while [ $(( ${#payload} % 4 )) -ne 0 ]; do payload="${payload}="; done
    if ! BUCKET="$(base64 -d <<< "$payload" | jq -er '.username | strings | select(length > 0)')"; then
        echo "Token does not contain a valid username; set BUCKET explicitly" >&2
        exit 1
    fi
fi

request="$(jq -n \
    --arg path "$DESTINATION_PATH" \
    --arg account "$SCHEDULER_ACCOUNT" \
    --argjson size "$UPLOAD_FILE_SIZE" \
    '{path: $path, account: $account, transferDirectives: {transferMethod: "s3", accessMethod: "sts", fileSize: $size}}')"
response="$(curl -fsS --location --globoff \
    "${F7T_URL}/filesystem/${F7T_SYSTEM}/transfer/upload" \
    --header "Content-Type: application/json" \
    --header "Authorization: Bearer $ACCESS_TOKEN" \
    --data "$request")"

if ! ACCESS_KEY_ID="$(jq -er '.transferDirectives.stsCredentials.accessKeyId | strings | select(length > 0)' <<< "$response")" ||
   ! SECRET_ACCESS_KEY="$(jq -er '.transferDirectives.stsCredentials.secretAccessKey | strings | select(length > 0)' <<< "$response")" ||
   ! SESSION_TOKEN="$(jq -er '.transferDirectives.stsCredentials.sessionToken | strings | select(length > 0)' <<< "$response")"; then
    echo "Upload response did not contain valid STS credentials" >&2
    exit 1
fi
if ! MAX_PART_SIZE="$(jq -er '.transferDirectives.maxPartSize | select(type == "number" and . > 0 and floor == .)' <<< "$response")"; then
    echo "Upload response did not contain a valid maxPartSize" >&2
    exit 1
fi
PART_COUNT=$(( (UPLOAD_FILE_SIZE - 1) / MAX_PART_SIZE + 1 ))
if [ "$MAX_PART_SIZE" -gt 5368709120 ] || [ "$PART_COUNT" -gt 10000 ] || \
   { [ "$PART_COUNT" -gt 1 ] && [ "$MAX_PART_SIZE" -lt 5242880 ]; }; then
    echo "Invalid multipart upload size or part count: $MAX_PART_SIZE bytes, $PART_COUNT parts" >&2
    exit 1
fi

encoded_bucket="$(jq -rn --arg value "$BUCKET" '$value | @uri')"
encoded_key="$(jq -rn --arg value "$OBJECT_KEY" '$value | split("/") | map(@uri) | join("/")')"
object_url="${S3_URL%/}/${encoded_bucket}/${encoded_key}"
tmp_dir="$(mktemp -d)"
part_file="${tmp_dir}/part"
headers_file="${tmp_dir}/headers"
response_file="${tmp_dir}/response"
auth_file="${tmp_dir}/auth"
upload_id=""
encoded_upload_id=""

s3_request() {
    local method="$1" url="$2"
    shift 2
    curl -fsS --path-as-is --aws-sigv4 "aws:amz:${S3_REGION}:s3" \
        --config "$auth_file" \
        --request "$method" "$@" "$url"
}

cleanup() {
    if [ -n "$upload_id" ]; then
        echo "Aborting unfinished multipart upload" >&2
        if ! s3_request DELETE "${object_url}?uploadId=${encoded_upload_id}" -o /dev/null; then
            echo "Failed to abort multipart upload" >&2
        fi
    fi
    rm -f -- "$part_file" "$headers_file" "$response_file" "$auth_file"
    rmdir -- "$tmp_dir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$ACCESS_KEY_ID$SECRET_ACCESS_KEY$SESSION_TOKEN" == *$'\n'* ]] || \
   [[ "$ACCESS_KEY_ID$SECRET_ACCESS_KEY$SESSION_TOKEN" == *$'\r'* ]]; then
    echo "STS credentials contain invalid line breaks" >&2
    exit 1
fi
auth_user="${ACCESS_KEY_ID}:${SECRET_ACCESS_KEY}"
auth_user="${auth_user//\\/\\\\}"
auth_user="${auth_user//\"/\\\"}"
auth_token="${SESSION_TOKEN//\\/\\\\}"
auth_token="${auth_token//\"/\\\"}"
printf 'user = "%s"\nheader = "x-amz-security-token: %s"\n' \
    "$auth_user" "$auth_token" > "$auth_file"
chmod 600 "$auth_file"

echo "Starting multipart upload to s3://${BUCKET}/${OBJECT_KEY}"
s3_request POST "${object_url}?uploads=" -o "$response_file"
upload_id="$(python3 -c '
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
upload_id = next((e.text for e in root.iter() if e.tag.split("}")[-1] == "UploadId"), None)
if root.tag.split("}")[-1] != "InitiateMultipartUploadResult" or not upload_id:
    sys.exit("S3 did not return a multipart upload ID")
print(upload_id)
' "$response_file")"
encoded_upload_id="$(jq -rn --arg value "$upload_id" '$value | @uri')"

etags_xml=""
for ((part_id = 1; part_id <= PART_COUNT; part_id++)); do
    offset=$(( (part_id - 1) * MAX_PART_SIZE ))
    dd if="$DATA_FILE" of="$part_file" bs=1048576 \
        iflag=skip_bytes,count_bytes skip="$offset" count="$MAX_PART_SIZE" status=none
    expected_size=$(( UPLOAD_FILE_SIZE - offset ))
    if [ "$expected_size" -gt "$MAX_PART_SIZE" ]; then expected_size="$MAX_PART_SIZE"; fi
    if [ "$(stat --printf '%s' "$part_file")" -ne "$expected_size" ]; then
        echo "File size changed while preparing part ${part_id}" >&2
        exit 1
    fi
    echo "Uploading part ${part_id}/${PART_COUNT}"
    s3_request PUT "${object_url}?partNumber=${part_id}&uploadId=${encoded_upload_id}" \
        --upload-file "$part_file" -D "$headers_file" -o "$response_file"
    etag="$(awk 'tolower($1) == "etag:" {sub(/^[^:]*:[[:space:]]*/, ""); sub(/\r$/, ""); value=$0} END {print value}' "$headers_file")"
    if [ -z "$etag" ]; then
        echo "S3 did not return an ETag for part ${part_id}" >&2
        exit 1
    fi
    etag="${etag//&/\&amp;}"
    etag="${etag//</\&lt;}"
    etag="${etag//>/\&gt;}"
    etags_xml="${etags_xml}<Part><PartNumber>${part_id}</PartNumber><ETag>${etag}</ETag></Part>"
done

echo "Completing multipart upload"
complete_xml="<CompleteMultipartUpload xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\">${etags_xml}</CompleteMultipartUpload>"
s3_request POST "${object_url}?uploadId=${encoded_upload_id}" \
    --header "Content-Type: application/xml" --data "$complete_xml" -o "$response_file"
python3 -c '
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
if root.tag.split("}")[-1] != "CompleteMultipartUploadResult":
    code = next((e.text for e in root.iter() if e.tag.split("}")[-1] == "Code"), "unknown")
    sys.exit(f"S3 multipart completion failed: {code}")
' "$response_file"
upload_id=""
echo "Upload complete: s3://${BUCKET}/${OBJECT_KEY}"
echo "No transfer job was submitted; the object remains in S3."

