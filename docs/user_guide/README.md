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

FirecREST provides two resources for transferring files:

- [`/filesystem/{system_name}/ops/download`](https://eth-cscs.github.io/firecrest-v2/openapi/#/filesystem/get_download_filesystem__system_name__ops_download_get)[`[|upload]`](https://eth-cscs.github.io/firecrest-v2/openapi/#/filesystem/post_upload_filesystem__system_name__ops_upload_post) for small files (up to 5MB by [default](../setup/conf/#dataoperation)) that can be uploaded or downloaded directly, and
- [`/filesystem/{system_name}/transfer/download`](https://eth-cscs.github.io/firecrest-v2/openapi/#/filesystem/post_download_filesystem__system_name__transfer_download_post)[`[|upload]`](https://eth-cscs.github.io/firecrest-v2/openapi/#/filesystem/post_upload_filesystem__system_name__transfer_upload_post) for large files that can be transferred depending the `transfer_method` chosen (if configured in the FirecREST instalation).

    It creates a job in the scheduler to make an asynchronous data transfer managed by the HPC center. Supported values for `transfer_method` are

    - `s3`: files must first be transferred to a staging storage system (e.g., S3) before being moved to their final location on the HPC filesystem.
    - `streamer`: it's a point-to-point data transfer using the [`firecrest-streamer`](https://pypi.org/project/firecrest-streamer/) client
    - `wormhole`: it's a point-to-point data transfer using the [`Magic Wormhole`](https://magic-wormhole.readthedocs.io/en/latest/welcome.html) client

!!! Note
    Availability of the transfer methods in the FirecREST installation depends on the configuration. You can check the [`status/systems`](https://eth-cscs.github.io/firecrest-v2/openapi/#/status/get_systems_status_systems_get) endpoint to get information about which `data_transfer` method is supported by your HPC provider.

When requesting a large file download, FirecREST returns a `jobId` and information about how to download the file. This information will be shown depending on the transfer method used:

### Using `s3` transfer method

#### S3 download

Once the remote job is completed, the file is temporary stored in the S3 object storage. Then, users can retrieve the file using the provided `download_url` directly from the S3 interface.

!!! example "Download a file using `streamer` transfer method"
    ```sh
    $ curl --request POST <firecrest_url>/filesystem/<system>/transfer/download \
    --header "Authorization: Bearer <token>" --header "Content-Type: application/json" \
    --data '{
        "path": "/path/to/remote/file",
        "transfer_directives": {
            "transfer_method": "s3"
        }
    }'

    {
        "transferJob": {
            "jobId": <jobId>,
            "system": "<system>",
            ...
        },
        "transferDirectives": {
            "transfer_method": "s3",
            "download_url": "<url>"
        }
    }
    ```

#### S3 upload

Given that FirecREST utilizes a storage service based on [S3 as staging area](../setup/arch/external_storage/), the upload is limited by the constraints on S3 server. In this case, for files larger than 5GB the file to be uploaded needs to be split in chunks, which complicates the file upload.

To address this, we have created a set of examples in different programming and scripting languages, described bellow:

- `s3` Upload with Python3: this is the easiest way of using FirecREST. See [FirecREST SDK section](#firecrest-sdk) below for more information and detailed examples.

- `s3` Upload with Bash: [Detailed example.](file_transfer_bash/README.md)

- `s3` Upload with .NET: [Detailed example.](file_transfer_dotnet/README.md)

!!! info "Need more examples?"
    If you need examples for your particular S3 use case (ie, using a different language than the listed above), feel free to open an [issue on GitHub](https://github.com/eth-cscs/firecrest-v2/issues/new). We'd be happy to create one for you.

### Using `streamer` transfer method

#### Streamer download {#streamer-download}

In order to use the `streamer` transfer method, users must install the [`firecrest-streamer`](https://pypi.org/project/firecrest-streamer/) tool.

!!! example "Download a file using `streamer` transfer method"
    ```sh
    $ curl --request POST <firecrest_url>/filesystem/<system>/transfer/download \
    --header "Authorization: Bearer <token>" --header "Content-Type: application/json" \
    --data '{
        "path": "/path/to/remote/file",
        "transfer_directives": {
            "transfer_method": "streamer"
        }
    }'

    {
        "transferJob": {
            "jobId": <jobId>,
            "system": "<system>",
            ...
        },
        "transferDirectives": {
            "transfer_method": "streamer",
            "coordinates": "<coordinates>"
        }
    }
    ```

!!! info
    The file selected will be available for downloading as long as the job is running in the scheduler. Additionally, users can check the `waitTimeout` and `inboundTransferLimit` parameters in the call to `GET /status/systems` to perform a better data transfer process.

After getting the response, you can use the secret `coordinates` in the execution of the `streamer` command to complete the download to the local system.

!!! warning
    Keep the secret `coordinates` secured: these are used to uniquely transfer data between a `streamer` client and a specific file in the remote filesystem. If you share the credentials with somebody else, they could move the data on your behalf.

!!! example "Using `firecrest-streamer` tool to download a file from a remote system"
    ```sh
    $ streamer receive --coordinates <coordinates> --path /path/to/local/file
    Transfering 1.0GiB...
     |████████████████████████████████████████| 100.0%
    File /path/to/local/file received successfully.
    ```

#### Streamer upload

Using the same method as for the [download](#streamer-download) you can `send` data to upload files from your local system to the cluster.

After receiving the secrets `coordinates`, you can use the `streamer` to upload the file to the requested target:

!!! example "Upload data using `streamer`"
    ```bash
    $ streamer send --coordinates <coordinates> --path /path/to/local/file
    Transfering 1.0GiB...
    |████████████████████████████████████████| 100.0%
    File file sent successfully.
    ```

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