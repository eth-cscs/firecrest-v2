
### Uploading Large Files
For large file uploads, FirecREST provides multi part upload URLs, the number of URLs depends on the file size. The user must split the file accordingly and upload each part to the assigned URL.

Once all parts have been uploaded, the user must call the provided complete upload URL to finalize the transfer. After completion, a remote job moves the file from the staging storage to its final destination.

#### Multi part upload example

The first step is to determine the size of your large file, expressed in bytes. A reliable method is to use the command: `stat --printf "%s" "$LARGE_FILE_NAME"`.

Then call the `/filesystem/{system}/transfer/upload` endpoint as following.

!!! example "Call to transfer/upload to activate the multipart protocol"
    ```bash
    curl -s --location --globoff "${F7T_URL}/filesystem/${F7T_SYSTEM}/transfer/upload" \
    --header "Content-Type: application/json" \
    --header "Authorization: Bearer $ACCESS_TOKEN" \
    --data "{
        \"path\":\"${DESTINATION_PATH}\",
        \"fileName\":\"${LARGE_FILE_NAME}\",
        \"fileSize\":\"${LARGE_FILE_SIZE_IN_BYTES}\"
    }"
    ```

The JSON response from this call follows the structure shown below. FirecREST calculates the number of parts the file must be split into, based on the provided file size and the `maxPartSize` setting. Each part is assigned a number from <i>1</i> to <i>n</i> and must be uploaded using the presigned URLs listed in `partsUploadUrls`. Once all parts have been successfully uploaded, the presigned URL in `completeUploadUrl` is used to finalize the upload sequence and initiate the transfer of the complete data file from S3 to its final destination.

!!! example "FirecREST response from `/filesystem/{system}/transfer/upload` endpoint"
    ```json
    {
    "transferJob": {
        "jobId": nnnnnnnnn,
        "system": "SYSTEM",
        "workingDirectory": "/xxxxxxxxx",
        "logs": {
            "outputLog": "/xxxxxxxx.log",
            "errorLog": "/xxxxxxxxx.log"
        }
    },
    "partsUploadUrls": [
        "https://part1-url", "https://part2-url", "https://part3-url"
    ],
    "completeUploadUrl": "https://upload-complete-url",
    "maxPartSize": 1073741824
    }
    ```
Given the `maxPartSize` field in the `/filesystem/{system}/transfer/upload` end-point response, split your large file consequently:

!!! example "Split large file to upload"
    ```bash
    $ split "$LARGE_FILE_NAME" -b "$maxPartSize" --numeric-suffixes=1
    ```

This will divide your large file in a set of parts numbered from <i>x01</i>,<i>x02</i>, etc. to the number of parts that the S3 multipart upload protocol expects. The number of split parts must match the number of items in the `partsUploadUrls`list.

Upload each part in the correct order. After a successful upload, S3 responds with an `ETag`, which is a checksum of that specific part. This value is essential for completing the multipart upload, so be sure to record it.

The example below demonstrates a simple sequential upload. However, this approach is not mandatory, since S3 fully supports uploading parts in parallel.

!!! example "Upload parts call"
    ```bash
    part_id=1
    etags_xml=""
    while read -r part_url; do
        # Generate the name of the part file sequentially
        part_file=$(printf "%s/x%02d" $PARTS_DIR ${part_id})
        # Upload data with curl and extract ETag
        if line=$(curl -f --show-error -D - --upload-file "$part_file" "$part_url" | grep -i "^ETag: " ) ;
        then
            etag=$(echo $line | awk -F'"' '{print $2}')
            etags_xml="${etags_xml}<Part><PartNumber>${part_id}</PartNumber><ETag>\"${etag%|*}\"</ETag></Part>"
        else
            echo "Error uploading part ${part_id}"
        fi
        part_id=$(( part_id + 1 ))
    done <<< "$(echo "$partsUploadUrls" | jq -r '.[]')"

    # Prepare ETag's XML collection
    complete_upload_xml="<CompleteMultipartUpload xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\">${etags_xml}</CompleteMultipartUpload>"
    ```
!!! note
    Note: The `ETags` have been assembled into an XML structure, as required by the S3 multipart upload protocol. This format ensures the upload can be finalized correctly. The XML must strictly follow the expected schema, including XML namespace, quoted `ETag` values and integer `PartNumber` entries.

!!! example "`Etag` collection's XML."
    ```xml
    <CompleteMultipartUpload
        xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <Part>
            <PartNumber>1</PartNumber>
            <ETag>"b93fa37618435783645da0f851497506"</ETag>
        </Part>
        <Part>
            <PartNumber>2</PartNumber>
            <ETag>"f3f341e6043429eb010fa335f0697390"</ETag>
        </Part>
        <Part>
            <PartNumber>3</PartNumber>
            <ETag>"f621481ce07eddab98291227f81d8248"</ETag>
        </Part>
    </CompleteMultipartUpload>
    ```


Complete the upload by calling the presigned `completeUploadUrl` as in the example below. Pass the XML collection of ETags as body data.

!!! example "Complete upload call"
    ```
    curl -f --show-error -i -w "%{http_code}" -H "Content-Type: application/xml" -d "$complete_upload_xml" -X POST $complete_upload_url

    ```
