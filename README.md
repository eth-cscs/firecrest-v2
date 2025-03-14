# FirecREST v2

A lightweight REST API for accessing HPC resources.

FirecREST is a high performance proxy providing a standardized interface to access HPC infrastructures from the web, with authentication and authorization, supporting multiple schedulers, storages, and filesystems types.

## Features

-	🔐 Authentication and authorization layer integrating [OAuth v2](https://oauth.net/2/) and [OpenFGA](https://openfga.dev/)
- ⚡ High-performance RESTful API powered by [asyncIO](https://docs.python.org/3/library/asyncio.html)
-	✨ Abstracts underlying HPC technology (schedulers, filesystems, storage, etc.)
-	📡 Async SSH connection pool enabling high-throughput regime
-	🩺 Integrated HPC cluster health checker
-	💠 Modular architecture with a lightweight and modern stack




# FirecREST v2 Demo

The FirecREST demo allows you to run FirecREST on your machine and connect to your local HPC cluster using your personal credentials.
This setup is for *illustrative and evaluation purposes only* and is *not intended for production use*.

## Running the FirecREST v2 Demo  

Ensure that [Docker](https://www.docker.com/) is installed and running on your machine, then execute the following command to start the FirecREST v2 demo container:

```console
docker run -p 8025:8025 -p 5025:5025  -p 3000:3000 --pull always ghcr.io/eth-cscs/firecrest-v2-demo:latest
```

Once the container is running, open your browser and navigate to:

➡️ **[http://localhost:8025/](http://localhost:8025/)**


# Documentation

### API Reference: [OpenAPI Swagger](https://eth-cscs.github.io/firecrest-v2/openapi/)
### K8s Deployment: [Helm Charts](https://eth-cscs.github.io/firecrest-v2/)


# Running FirecREST v2 with Docker-Compose

To test and debug FirecREST locally we provide a local Docker environment that already contain all required dependencies (Slurm cluster, identity provider, storage, etc.). Please make sure [Docker](https://www.docker.com/) is installed and running on your machine.

To start a local Firecrest environment in VS Code right click the selected environment (e.g."docker-compose.yml") and select "Compose up"

Alternatively, use the command line:
```console
docker compose -f docker-compose.yml up
```
## Local Environment

The environment comes with an identity provider (Keycloack) for authentication, a dummy hpc cluster (with Slurm) and a storage service.


### Users

The environment comes with two predefined users:

- **fireuser** this account represents an actual user
- **firesrv** this account represents a service account 


## Accessing Firecrest

- The Firecrest endpoints are accessible at: http://localhost:8000/
- The Firecrest API swagger: http://localhost:8000/docs and http://localhost:8000/redoc

To access most of the end-points you need an authorization token. Firecrest authorization is based on the standard [Oauth2 Client Credentials Flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow)


All local environments come with pre-configured test credentials:

```credentials
client: firecrest-test-client
secret: wZVHVIEd9dkJDh9hMKc6DTvkqXxnDttk
```

To optain an access token you can either use the Authorize button in the [swagger documentation](http://localhost:8000/docs) or directly access Keycloack's Oauth2 token end-point:  http://localhost:8080/auth/realms/kcrealm/protocol/openid-connect/token


# Development

The repository comes with VS Code settings (.vscode) to facilitate running and debugging a local instance of FirecREST v2.
All necessary VS Code extensions will be listed as recommended and are defined in .vscode/extensions.json.

## Set-up Python Virtual environement

Install python3.12 on your machine.

Create a virtual environment:
```console
python3.12 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-testing.txt
```

Re-lauch VS Code, the virtual env should automatically be enabled on restart.

#### Advanced

To update the local dependencies:
```console
python3 -m pip install -r requirements.txt
```

## Running Tests
From the FirecREST root folder run pytest to execute all unit tests.
```console
source .venv/bin/activate
pip install -r ./requirements.txt -r ./requirements-testing.txt
pytest
```


## Debugging FirecREST v2

The project comes with preconfigured VS Code "Run and Debug" configurations.
The configuration includes proper path mapping to enable breakpoints.

In the VS Code "Run and Debug" tab, select Firecrest API [Docker Compose] hit the play button.


## Accessing Support Services

The Docker environments also include third-party services required by Firecrest to run.

### Keycloak

To access Keycloak’s admin console, navigate to: http://localhost:8080/auth/admin with user-name:admin and password:admin2

Retrieve JWT keys to be used by Slurm for token verification: http://localhost:8080/auth/realms/kcrealm/protocol/openid-connect/certs

Slurm and Firecrest requires the JWT token to inclue the following fields:
- iat: Unix timestamp of creation date.
- exp: Unix timestamp of expiration date.
- username: Slurm UserName ( POSIX.1-2017 User Name ).

Keycloak will set the preffered_username as the Service Accout User associated with the client credentials used to create the token.
To add the username claim to the token:

- Create a Client Scope (e.g. firecrest_v2) with a Mapper. The mapper should add a token claim with name 'username' mapping the user attribute 'scheduler_user'
- To each Firecrest client add the newly created client scope.
- To each Firecrest client service account add the scheduler_user attribute with the value being the scheduler user to impersonate.


### Slurm Dummy Cluster

To ssh into the Slurm Dummy Cluster you can use the fireuser

```console

ssh-keygen -p -s build/environment/keys/fireuser-key -n fireuser -I fireuser -f user-key-cert.pub build/environment/keys/fireuser.pub
chmod 0400 build/environment/keys/fireuser.pub
ssh -i build/environment/keys/fireuser.pub fireuser@localhost -p 2222

```


