# Architecture of FirecREST

FirecREST is presented as a simple interface to access HPC resources with an HTTP enabled API.

In this chapter it is shown how FirecREST is configured from the architectural point of view to provide this integration with HPC clusters, workload manager and schedulers, authentication, data transfer, etc.

## HPC Systems and workload manager and schedulers

[System Docs](systems/README.md)

## Authentication/Authorization

## Health Checks and liveness probes

## Data Transfers

FirecREST handles data transfer up to 5 TB. See how this is done [here](./external_storage/README.md)
