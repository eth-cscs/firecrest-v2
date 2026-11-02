#!/bin/bash
set -euo pipefail
# -----------------------------------------------------------------------------
# Tests the temporary STS credentials returned by the FirecREST upload endpoint
# directly against the S3 storage (e.g. the RustFS container).
# Requires: curl >= 7.75 (for --aws-sigv4), jq
#
# Optional environment variables:
#   S3_URL     S3 endpoint reachable from this machine (default: http://localhost:9000)
#   S3_REGION  S3 region (default: us-east-1)
#   BUCKET     Bucket name (default: preferred_username claim of the access token)
# -----------------------------------------------------------------------------
# Arguments
if [ "$#" -lt "3" ];
then
    echo "usage: $0 <system> <destination> <env_file> [<scheduler_account>]"
    exit 1
fi
F7T_SYSTEM="$1"
DESTINATION_PATH="$2"
ENV_FILE="$3"
SCHEDULER_ACCOUNT=${4:-staff}
if [ ! -f "$ENV_FILE" ]; then
    echo "$ENV_FILE not found"
    exit 2
fi

S3_URL="${S3_URL:-http://localhost:9000}"
S3_REGION="${S3_REGION:-us-east-1}"

# -----------------------------------------------------------------------------
# Load environment
source "$ENV_FILE"

# Get Access Token
echo "Get access token"
response="$(curl -s --request POST \
--url "$TOKEN_URI" \
--header "content-type: application/x-www-form-urlencoded" \
--data "grant_type=client_credentials" \
--data "client_id=$CLIENT_ID" \
--data "client_secret=$CLIENT_SECRET")"
ACCESS_TOKEN="$(echo "$response" | jq -r '.access_token')"
if [ -z "$ACCESS_TOKEN" ] || [ "$ACCESS_TOKEN" = "null" ]; then
    >&2 echo "Error: failed to obtain access token. Response: $response"
    exit 3
fi

# The bucket is named after the user
if [ -z "${BUCKET:-}" ]; then
    payload="$(echo "$ACCESS_TOKEN" | cut -d. -f2 | tr '_-' '/+')"
    # Restore base64 padding stripped by the JWT encoding
    while [ $(( ${#payload} % 4 )) -ne 0 ]; do payload="${payload}="; done
    BUCKET="$(echo "$payload" | base64 -d | jq -r '.username')"
fi
echo "Bucket: $BUCKET"

# -----------------------------------------------------------------------------
# Request an upload to get the STS credentials (a 1 byte upload is enough)
raw_response=$(curl -s -w "\n%{http_code}" --location --globoff "${F7T_URL}/filesystem/${F7T_SYSTEM}/transfer/upload" \
--header "Content-Type: application/json" \
--header "Authorization: Bearer ${ACCESS_TOKEN}" \
--data "{
  \"path\":\"${DESTINATION_PATH}\",
  \"fileName\":\"sts_test.data\",
  \"account\":\"${SCHEDULER_ACCOUNT}\",
  \"transferDirectives\": {
      \"fileSize\":\"1\",
      \"transferMethod\":\"s3\"
  }
}")
http_status="${raw_response##*$'\n'}"
response="${raw_response%$'\n'*}"
if [[ ! "$http_status" =~ ^2[0-9]{2}$ ]]; then
    >&2 echo "Upload request failed with HTTP status: $http_status. Response: $response"
    exit 4
fi

sts="$(echo "$response" | jq -r '.transferDirectives.stsCredentials')"
if [ -z "$sts" ] || [ "$sts" = "null" ]; then
    >&2 echo "No stsCredentials in the response: $response"
    exit 5
fi
ACCESS_KEY_ID="$(echo "$sts" | jq -r '.accessKeyId')"
SECRET_ACCESS_KEY="$(echo "$sts" | jq -r '.secretAccessKey')"
SESSION_TOKEN="$(echo "$sts" | jq -r '.sessionToken')"
echo "STS credentials received (expiration: $(echo "$sts" | jq -r '.expiration'))"

# -----------------------------------------------------------------------------
# Test the credentials against the storage
s3_request() {
    # usage: s3_request <method> <path> [<curl options>...]
    local method="$1" path="$2"
    shift 2
    curl -s -o /dev/null -w "%{http_code}" -X "$method" \
        --aws-sigv4 "aws:amz:${S3_REGION}:s3" \
        --user "${ACCESS_KEY_ID}:${SECRET_ACCESS_KEY}" \
        -H "x-amz-security-token: ${SESSION_TOKEN}" \
        "$@" "${S3_URL}/${path}"
}

check() {
    # usage: check <description> <status> <expected status>
    if [ "$2" == "$3" ]; then
        echo "[ OK ] $1 ($2)"
    else
        >&2 echo "[FAIL] $1: got HTTP $2, expected $3"
        exit 6
    fi
}

OBJECT="sts-test/$(date +%s).txt"
check "List bucket"   "$(s3_request GET "${BUCKET}?list-type=2")" 200
check "Put object"    "$(s3_request PUT "${BUCKET}/${OBJECT}" --data-binary "sts test")" 200
check "Get object"    "$(s3_request GET "${BUCKET}/${OBJECT}")" 200
check "Delete object" "$(s3_request DELETE "${BUCKET}/${OBJECT}")" 204

# Credentials must be restricted to the user bucket
OTHER_BUCKET="${BUCKET}-other"
other_status="$(s3_request GET "${OTHER_BUCKET}?list-type=2")"
if [ "$other_status" == "403" ]; then
    echo "[ OK ] Access to a different bucket is denied (403)"
else
    >&2 echo "[WARN] Access to ${OTHER_BUCKET} returned HTTP ${other_status}, expected 403"
fi

echo "STS credentials test completed"
