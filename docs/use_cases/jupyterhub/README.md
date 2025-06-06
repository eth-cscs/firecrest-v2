# JupyterHub FirecRESTSpawner

For most setups, installing JupyterHub in HPC Centers requires the service to be installed on premises, while sharing workload scheduler admin keys and sudo access.

Using FirecREST to spawn jobs as an abstraction for workload schedulers, enables HPC sysadmins to avoid these issues, allowing the service to be installed in cloud providers, avoiding the use of admin credentials installed in the service, and to use the same setup for systems with different schedulers and Identity Providers.

This tutorial explains how to run [JupyterHub](https://jupyterhub.readthedocs.io/en/stable/) with [FirecRESTSpawner](https://github.com/eth-cscs/firecrestspawner) using the [Docker demo of FirecREST API v2](https://github.com/eth-cscs/firecrest-v2).

FirecRESTSpawner is a tool for launching Jupyter Notebook servers from JupyterHub on HPC clusters through FirecREST.
It supports both [version 1](https://firecrest.readthedocs.io/en/stable/) and [version 2](https://github.com/eth-cscs/firecrest-v2) of the API.
It can be deployed on Kubernetes as part of JupyterHub and configured to target different systems.

In this tutorial, we will set up a simplified environment on a local machine, including:

- a [Docker Compose](https://docs.docker.com/compose) deployment of FirecREST, a single-node Slurm cluster and a [Keycloak](https://www.keycloak.org) server which will be used as identity provider for the authentication
- a local installation of JupyterHub, configured to launch notebooks on the Slurm cluster

This deployment not only demonstrates the use case but also serves as a platform for testing and developing FirecRESTSpawner.

## Requirements

For this tutorial you will need

- a recent installation of Docker, which includes the `docker compose` command (or the older `docker-compose` command line tool)
- a Python installation (version 3.9 or higher)

## Deployment of FirecREST and Slurm cluster

This tutorial builds on the Docker demo of FirecREST.
We will use the small [docker-compose-jhub.yaml](./docker-compose-jhub.yaml) file to override some settings in the FirecREST demo.
This can be done by passing both files to the `docker compose` command.

First, we clone the FirecREST repository

!!! example "Cloning FirecREST official repo"
    ```bash
    git clone https://github.com/eth-cscs/firecrest-v2.git
    ```

and then launch the deployment

!!! example "Launch docker compose"
    ```bash
    cd firecrest-v2
    export JHUB_DOCKERFILE_DIR=./docs/use_cases/jupyterhub/
    docker compose -f docker-compose.yml -f $JHUB_DOCKERFILE_DIR/docker-compose-jhub.yaml up
    ```

This step takes a few minutes. In the meanwhile we can install JupyterHub on a local virtual environment.

### Install JupyterHub and FirecRESTSpawner

An easy way to install JupyterHub is via [Miniconda](https://docs.anaconda.com/miniconda/install/).
We need to [download the Miniconda installer](https://docs.anaconda.com/miniconda/install/) for our platforms and install it using the following command (replace `<arch>` with the architecture on your workstation, for instance `Linux-x86_64` or `MaxOSX-arm64`):

!!! example "Install Miniconda"
    ```bash
    bash Miniconda3-latest-<arch>.sh -p /path/to/mc-jhub -b
    ```

Here we use `-p` to pass the absolute path to the install directory and `-b` to accept the [terms of service](https://legal.anaconda.com/policies/en/).

We can activate our conda base environment and install `configurable-http-proxy`, `JupyterHub` and `FirecRESTSpawner`:

!!! example "Install JupyterHub using FirecRESTSpawner"
    ```bash
    . /path/to/mc-jhub/bin/activate
    conda install -y configurable-http-proxy
    pip install --no-cache jupyterhub==4.1.6 pyfirecrest==3.0.1 SQLAlchemy==1.4.52 oauthenticator==16.3.1 python-hostlist==1.23.0
    git clone https://github.com/eth-cscs/firecrestspawner.git
    cd firecrestspawner
    git checkout fcv2
    pip install --no-cache .
    ```

## Back to the deployment

Once the images have been built, you can check that all containers are running

!!! example "Check containers are running"
    ```bash
    $ docker compose -p firecrest-v2 ps --format 'table {{.ID}}\t{{.Name}}\t{{.State}}'
    ```

That should show something like this

!!! example
    ```bash
    CONTAINER ID   NAME                       STATE
    fd8b1575bf18   firecrest-v2-firecrest-1   running
    4a6e4c3d089d   firecrest-v2-keycloak-1    running
    36f8d98f3b67   firecrest-v2-minio-1       running
    85de3b4afe95   firecrest-v2-slurm-1       running
    ```

When we are done with the tutorial, the deployment can be shutdown by pressing `ctrl+c` and then:

!!! example "Shut down docker containers"
    ```
    cd firecrest-v2
    docker compose -f docker-compose.yml -f /path/to/tutorial/docker-compose-jhub.yaml down
    ```

### Setting up the authorization

A requirement for running JupyterHub with FirecRESTSpawner is to use an authenticator that prompts users for login and password in exchange for an [OIDC/OAuth2 access token](https://datatracker.ietf.org/doc/html/rfc7519).
That token is then be passed to the spawner, allowing users to authenticate with FirecREST when submitting, stopping or polling for jobs.
For this purpose, we will use an [Authorization Code Flow](https://datatracker.ietf.org/doc/html/rfc6749#section-4.1) client, which we need to create on the Keycloak web interface.

!!! info "More on AuthN"
    For more information on how FirecREST uses the authentication layer, follow this [documentation](../../setup/arch/auth/README.md).  

Let's go to the [Clients page](http://localhost:8080/auth/admin/master/console/#/master/clients) in Keycloak (username: `admin` and password: `admin2`) within the `kcrealm` realm.
We click on "Import client" and then on "Browse".
A file system explorer will open.
Navigate to the tutorial's directory, choose the [jhub-client.json](jhub-client.json) file and click on "Save".

Once that's done, the client `jhub-client` can be seen listed on the "Clients" tab of the side panel.

## Launching JupyterHub

The [configuration file](jupyterhub-config.py) provided in this tutorial has all the settings needed for using JupyterHub with our deployment.

> Depending on the platform and Docker setup, you may need to adjust a few lines in the configuration to set the correct host IP address for the Docker bridge network.
> On most Linux systems, you can find this address with `ip addr show docker0`.
> It's typically `172.17.0.1`.
> If JupyterHub gets a timeout when launching a notebook, you can try replacing the two instances of `host.docker.internal` in the configuration by that ip.

Now we can run JupyterHub with

!!! example "Run JupyterHub locally"
    ```bash
    cd $JHUB_DOCKERFILE_DIR
    source /path/to/mc-jhub/bin/activate
    source env.sh
    jupyterhub --config jupyterhub-config.py --port 8003 --ip 127.0.0.1
    ```
Here we are sourcing the file [env.sh](env.sh) which defines environment variables needed by the spawner (more information can be found [here](https://firecrestspawner.readthedocs.io/en/latest/authentication.html)).
We use the port `8003` for the JupyterHub since the default one `8000` is already used for FirecREST in the deployment.
The IP address `127.0.0.1` is necessary to allow JupyterLab to connect back to the JupyterHub.

JupyterHub should be accessible in the browser at [http://localhost:8003](http://localhost:8003/) and it should be possible to launch notebooks on the slurm cluster.

To access the interface use the following credentials: 

- Username: `fireuser`
- Password: `password`
