# Getting started

## Quick start

The FirecREST demo allows you to run FirecREST on your machine and connect to your local HPC cluster using your personal credentials.
This setup is for *illustrative and evaluation purposes only* and is *not intended for production use*.

### Running the FirecREST v2 Demo Launcher

Ensure that [Docker](https://www.docker.com/) is installed and running on your machine, then execute the following command to start the FirecREST v2 demo container:

```console
docker run -p 8025:8025 -p 5025:5025  -p 3000:3000 --pull always ghcr.io/eth-cscs/firecrest-v2-demo:latest
```

Once the container is running, open your browser and navigate to:

➡️ **[http://localhost:8025/](http://localhost:8025/)**


## Trying FirecREST in a full docker environment

To test and debug FirecREST locally we provide a local Docker environment that already contain all required dependencies (Slurm cluster, identity provider, storage, etc.). Please make sure [Docker](https://www.docker.com/) is installed and running on your machine.

To start a local Firecrest environment in VS Code right click the selected environment (e.g."docker-compose.yml") and select "Compose up"

Alternatively, use the command line:
```console
docker compose -f docker-compose.yml up
```
### Local Environment

The environment comes with an identity provider (Keycloack) for authentication, a dummy hpc cluster (with Slurm) and a storage service.


#### Users

The environment comes with two predefined users:

- **fireuser** this account represents an actual user
- **firesrv** this account represents a service account 


#### Accessing Firecrest

- The Firecrest endpoints are accessible at: http://localhost:8000/
- The Firecrest API swagger: http://localhost:8000/docs and http://localhost:8000/redoc

To access most of the end-points you need an authorization token. Firecrest authorization is based on the standard [Oauth2 Client Credentials Flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow)


All local environments come with pre-configured test credentials:

```credentials
client: firecrest-test-client
secret: wZVHVIEd9dkJDh9hMKc6DTvkqXxnDttk
```

To obtain an access token you can either use the Authorize button in the [swagger documentation](http://localhost:8000/docs) or directly access Keycloack's Oauth2 token end-point:
```bash
CLIENT_ID="<client>"
CLIENT_SECRET="<secret>"
curl -X POST http://localhost:8080/auth/realms/kcrealm/protocol/openid-connect/token \
     -d "grant_type=client_credentials" -d "client_id=$CLIENT_ID" -d "client_secret=$CLIENT_SECRET" \
     -H "Content-Type: application/x-www-form-urlencoded" -H "Accept: */*"
```

### Example

- List filesystem
- Run a job

