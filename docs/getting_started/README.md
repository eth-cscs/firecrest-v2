# Getting started

## Quick start

The FirecREST demo allows you to run FirecREST on your laptop or workstation and connect to a functional HPC cluster using your personal credentials.

!!! warning
    This setup is for illustrative and evaluation purposes only and is not intended for production use.

### Running the FirecREST v2 Demo Launcher

Ensure that [Docker](https://www.docker.com/) is installed and running on your machine, then execute the following command to start the FirecREST v2 demo container:

!!! example "Run FirecREST demo launcher"
    ```bash
    $ docker run -p 8025:8025 -p 5025:5025  -p 3000:3000 --pull always ghcr.io/eth-cscs/firecrest-v2-demo:latest
    ```

Once the container is running, open your browser and navigate to:

➡️ **[http://localhost:8025/](http://localhost:8025/)**


## Trying FirecREST in a containerised environment

In addition, to test and debug FirecREST locally we provide a local Docker environment that already contains all required dependencies (an HPC cluster, identity provider, object storage, etc.). Please make sure [Docker](https://www.docker.com/) is installed and running on your machine.

!!!
    To start a local Firecrest environment in VSCode right click the selected environment (e.g. `docker-compose.yml`) and select "Compose up"

Alternatively, use the command line:

!!! example "Run development environment on CLI"
    ```bash
    $ git clone https://github.com/eth-cscs/firecrest-v2
    $ cd firecrest-v2
    $ docker compose -f docker-compose.yml up
    ```

### Local Environment

The environment comes with an OIDC/OAuth2 Identity Provider ([Keycloak](https://www.keycloak.org/)) for authentication, a dummy HPC cluster (with [Slurm](https://slurm.schedmd.com/documentation.html) as workload manager) and a storage service ([MinIO](https://min.io/product/s3-compatibility) with S3 interface).


#### Users

The environment comes with two predefined users:

- **fireuser** this account represents an actual user
- **firesrv** this account represents a service account 


#### Accessing Firecrest

- The Firecrest endpoints are accessible at: http://localhost:8000/
- The Firecrest API swagger: http://localhost:8000/docs and http://localhost:8000/redoc

To access most of the end-points you need an authorization token. Firecrest authorization is based on the standard [Oauth2 Client Credentials Flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow)


All local environments come with pre-configured test credentials:

!!! FirecREST credentials
    ```credentials
    client: firecrest-test-client
    secret: wZVHVIEd9dkJDh9hMKc6DTvkqXxnDttk
    ```

To obtain an access token you can either use the Authorize button in the [swagger documentation](http://localhost:8000/docs) or directly access Keycloak's OAuth2 token end-point:

!!! note
    We use for these examples [curl](https://curl.se/) and [jq](https://jqlang.org/) commands

???+ example "Obtain access token"
    ```bash
    $ CLIENT_ID="firecrest-test-client"
    $ CLIENT_SECRET="wZVHVIEd9dkJDh9hMKc6DTvkqXxnDttk"
    $ access_token$(curl -s -X POST http://localhost:8080/auth/realms/kcrealm/protocol/openid-connect/token \
    -d "grant_type=client_credentials" -d "client_id=$CLIENT_ID" -d "client_secret=$CLIENT_SECRET" \
    -H "Content-Type: application/x-www-form-urlencoded" -H "Accept: */*" | jq --raw-output ."access_token")
    $ echo $access_token
    eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJ1Xz.......
    ```

### API call examples

!!! note
    In this dev environment there are 2 clusters for testing: `cluster-slurm-ssh` and `cluster-slurm-api`. We will use the first one in this example

???+ example "List `$HOME` directory content"
    ```bash
        $ curl -s "http://localhost:8000/filesystems/cluster-slurm-ssh/ops/ls?path=/home/fireuser" \
        -H "Authorization: Bearer $access_token" | jq .
        {
            "output": [
                {
                    "name": "tmp",
                    "type": "d",
                    "linkTarget": null,
                    "user": "fireuser",
                    "group": "users",
                    "permissions": "rwxr-xr-x",
                    "lastModified": "2025-03-18T11:01:43",
                    "size": "4096"
                }
            ]
        }
    ```

??? example "Submit a job to the workload manager and scheduler"
    ```bash
    curl -X POST -s "http://localhost:8000/compute/cluster-slurm-ssh/jobs" \
        --json '{"job": {"script": "#!/bin/bash -l\nfor i in {1..100}\ndo\necho $i\nsleep 1\ndone", "working_directory": "/home/fireuser"}}'  \
        -H "Authorization: Bearer $access_token" -H "Content-Type: application/json" | jq .
    {
        "jobId": 5
    }
    ```

??? example "Check status of the job"
    ```bash
    curl -X GET -s "http://localhost:8000/compute/cluster-slurm-ssh/jobs/5" -H "Authorization: Bearer $access_token" -H "Content-Type: application/json" | jq .
    {
        "jobs": [
            {
            "jobId": 5,
            "name": "Count",
            "status": {
                "state": "COMPLETED",
                "stateReason": "None",
                "exitCode": 0,
                "interruptSignal": 0
            },
            "tasks": [
                {
                "id": "5.batch",
                "name": "batch",
                "status": {
                    "state": "COMPLETED",
                    "stateReason": null,
                    "exitCode": 0,
                    "interruptSignal": 0
                },
                "time": {
                    "elapsed": 101,
                    "start": 1742492131,
                    "end": 1742492232,
                    "suspended": 0,
                    "limit": null
                }
                }
            ],
            "time": {
                "elapsed": 101,
                "start": 1742492131,
                "end": 1742492232,
                "suspended": 0,
                "limit": 7200
            },
            "account": "staff",
            "allocationNodes": 1,
            "cluster": "cluster",
            "group": "users",
            "nodes": "localhost",
            "partition": "part01",
            "priority": 1,
            "killRequestUser": null,
            "user": "fireuser",
            "workingDirectory": "/home/fireuser"
            }
        ]
    }
    ```
