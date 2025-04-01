# FirecREST v2

FirecREST is an open-source, lightweight REST API for accessing HPC resources developed by the Swiss National Supercomputing Centre ([CSCS](https://www.cscs.ch/)).

FirecREST presents a high performance proxy providing a standardized interface to access HPC infrastructures from the web, with authentication and authorization, supporting multiple schedulers, storages, and filesystems types.

Using FirecREST, users and web developers can **automate** access to HPC resources and create client applications, pipelines, and workflow managers on the top of HPC with a standard and secure interface.

## Features

-	🔐 Authentication and authorization layer integrating [Open ID Connect (OIDC)](https://openid.net/developers/how-connect-works/)/[OAuth2](https://oauth.net/2/) and [OpenFGA](https://openfga.dev/)
- ⚡ High-performance RESTful API powered by [asyncIO](https://docs.python.org/3/library/asyncio.html)
-	✨ Abstracts underlying HPC technology (schedulers, filesystems, storage, etc.) relying in [REST API](https://restfulapi.net/) concept and [OpenAPI](https://www.openapis.org/) specification
-	📡 Async SSH connection pool enabling high-throughput regime
-	🩺 Integrated HPC cluster health checker
-	💠 Modular architecture with a lightweight and modern stack
- 💻 Easy to integrate with your code using [pyFirecREST](https://pyfirecrest.readthedocs.io/en/stable/) Python library

## Get involved

- Check out our [GitHub repository](https://github.com/eth-cscs/firecrest-v2), clone the repo, try the Demo environment, create issues, contribute, and more!

- Join the [FirecREST Slack community](https://firecrest-community.slack.com/) or contact us via [email](mailto:firecrest@cscs.ch)

## Start using FirecREST

- Follow the [Getting Started](getting_started/README.md) documentation to quickly start exploring the features of FirecREST first hand
- Browse the [Use Cases](use_cases/README.md), which brings cases of success applying FirecREST on different tools
- Check out the [OpenAPI specification](https://eth-cscs.github.io/firecrest-v2/openapi/) for the complete set of FirecREST endpoints
