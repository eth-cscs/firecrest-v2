# User Guide

## Authentication
FirecREST authentication follows the [OpenID Connect (OIDC)](https://auth0.com/docs/authenticate/protocols/openid-connect-protocol) standard.

To access most endpoints (see the [API reference](https://eth-cscs.github.io/firecrest-v2/openapi/)), you must provide a JWT authorization token in the `Authorization` header:

!!! example "Authorization header"
    ```
    Authorization: Bearer <token>
    ```

FirecREST authenticates users by verifying the JWT token’s signature against trusted certificates (see the [configuration](../setup/conf/README.md) section). If the JWT token is valid, FirecREST extracts the `username` or `preferred_username` claim to establish the user's identity and propagate it downstream (e.g., for SSH authentication).

To obtain a JWT token, you need a trusted Identity Provider that supports OAuth2 or OpenID Connect protocols. The FirecREST Docker Compose development environment (see the [Getting Started](../getting_started/README.md) section) includes a preconfigured [Keycloak](https://www.keycloak.org/) identity provider.

There are multiple grant flows available to obtain a JWT token. The most common ones are:

### Client Credentials Grant

This grant is used to authenticate an application (client) rather than an individual user. However, since HPC infrastructures typically require usage tracking, it is recommended to create a dedicated client for each user or project and assign a service account owned by the user/project to the client. 

**Important:**
Using the identity provider to associate a user or project with a client offers a secure and flexible way to map HPC internal users to FirecREST credentials:
**client credential ← service account ← user/project**

In this flow, the client submits its `client_id` and `client_secret` directly to the authorization server to obtain an access token and a refresh token.


!!! example "Obtain an access token"
    ```
    curl --request POST \
    --url 'http://localhost:8080/auth/realms/kcrealm/protocol/openid-connect/token' \
    --header 'content-type: application/x-www-form-urlencoded' \
    --data grant_type=client_credentials \
    --data client_id=firecrest-test-client \
    --data client_secret=wZVHVIEd9dkJDh9hMKc6DTvkqXxnDttk
    ```

**Note:** The above `curl` command is configured to work with the provided Docker Compose environment. 

!!! example "Expected output example"
    ```json
    {"access_token":"<token>","expires_in":300,"token_type":"Bearer","scope":"firecrest-v2 profile email"} 
    ```


### Authorization Code Grant

This grant is intended for web applications. The user's browser is redirected (HTTP 302) to the authorization server, which handles authentication (e.g., via username/password, two-factor authentication, etc.).

After successful authentication, the authorization server redirects the browser back to a pre-registered endpoint in the web application, passing an authorization code. The web application then uses its own credentials (`client_id` and `client_secret`) along with the authorization code to request an access token from the authorization server.


## API Reference

### Accessing HTTP RESTful Resources

The FirecREST API follows RESTful design principles, allowing access to the underlying resources through standard HTTP requests.

Each request consists of:

- **Endpoint (URL):** The address of the resource being accessed.
- **Method:** One of `GET`, `POST`, `PUT`, or `DELETE`, depending on the action.
- **Headers:** Metadata necessary for authorisation.
- **Body:** The request payload in JSON format.

Below is a quick overview of the methods:

| Method  | Description  |
|---------|-------------|
| `GET`   | Retrieves resources |
| `POST`  | Creates resources  |
| `PUT`   | Updates resources  |
| `DELETE`| Deletes resources  |

The request body format is specific to each call, the full list of available API calls and requests can be found here: **[API reference](https://eth-cscs.github.io/firecrest-v2/openapi/)**.


### Response Structure

Each FirecREST API response consists of:

- **Status Code:** Indicates the outcome of the request.
- **Headers:** Metadata related to the response.
- **Body:** The response data in JSON format.

Below is an overview of HTTP status codes and their meanings:

| Code  | Category        | Description  |
|-------|---------------|-------------|
| 1xx   | Informational  | Communicates protocol-level information |
| 2xx   | Success        | Indicates the request was successfully processed |
| 3xx   | Redirection    | Instructs the client to take additional action |
| 4xx   | Client Error   | Indicates an issue with the request sent by the client |
| 5xx   | Server Error   | Indicates an issue on the server's side |

### Resource Groups

FirecREST API endpoints are categorized into three groups:

| Group       | URL Prefix       | Description |
|------------|-----------------|-------------|
| **Status**   | `/status/...`    | Provides status information about FirecREST and underlying resources |
| **Compute**  | `/compute/...`   | Grants access to the job scheduler |
| **Filesystem** | `/filesystem/...` | Provides access to the filesystem |

### Targeting Systems

A single FirecREST instance can manage multiple HPC systems. Most endpoints require specifying which system to access by including the system name in the endpoint path.

For example:

!!! example "Endpoint path"
    ```plaintext
    /compute/{system_name}/jobs
    ```

The `{system_name}` should correspond to the cluster name provided in the FirecREST configuration.  Refer to the [configuration](../setup/conf/README.md) section for details.


### Full API Endpoints List

The complete list of FirecREST API endpoints is available here:  **[API reference](https://eth-cscs.github.io/firecrest-v2/openapi/)**

## Synchronous and Asynchronous Calls

Most FirecREST endpoints operate synchronously, meaning that the invoked operation is completed before a response is provided. All synchronous responses have a fixed timeout of 5 seconds. If the operation cannot be completed within this time limit, an error is returned.

A limited set of filesystem-specific operations are executed asynchronously. These calls are non-blocking, and a jobId is returned. It is the user’s responsibility to track the status of the remote job and retrieve the result upon completion.


All asynchronous endpoints are located under  `/transfer` and follow this path structure:

!!! example "Asynchronous transfers endpoint"
    ```
    /filesystem/{system_name}/transfer/...
    ```

## File transfer

FirecREST provides two methods for transferring files:
- Small files (up to 5MB by [default](../setup/conf/README.md)) can be uploaded or downloaded directly.
- Large files must first be transferred to a staging storage system (e.g., S3) before being moved to their final location on the HPC filesystem.

Small file transfer endpoints:
 - `/filesystem/{system_name}/ops/download`
 - `/filesystem/{system_name}/ops/upload`

 Large file transfer endpoints:
 - `/filesystem/{system_name}/transfer/download`
 - `/filesystem/{system_name}/transfer/upload`

### Downloading Large Files

When requesting a large file download, FirecREST returns a download URL and a jobId. Once the remote job is completed, the user can retrieve the file using the provided URL.

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

## File Transfer with .NET
[Detailed example.](file_transfer_dotnet/README.md)

## FirecREST SDK

[PyFirecREST](https://github.com/eth-cscs/pyfirecrest) is a Python library designed to simplify the implementation of FirecREST clients.

### Installation
To install PyFirecREST, run:

!!! example "Install `pyfirecrest`"
    ```bash 
    $ python3 -m pip install pyfirecrest
    ```

For more details, visit the [official documentation page](https://pyfirecrest.readthedocs.io).

#### List files example

!!! example "List files with `pyfirecrest`"
    ```python
    import firecrest as fc

    class MyAuthorizationClass:
        def get_access_token(self):
            return <TOKEN>

    client = fc.v2.Firecrest(firecrest_url=<firecrest_url>, authorization=MyAuthorizationClass())

    files = client.list_files("cluster", "/home/test_user")
    print(files)

    ```

More examples are available at: [pyfirecrest.readthedocs.io](https://pyfirecrest.readthedocs.io)