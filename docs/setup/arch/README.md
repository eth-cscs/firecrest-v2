# Architecture of FirecREST

FirecREST is presented as a simple interface to access HPC resources with an HTTP enabled API. 

In this chapter it is shown how FirecREST is configured from the architectural point of view to provide this integration with HPC clusters, workload manager and schedulers, authentication, data transfer, etc.

## The full picture

In the figure below it can be seen the different components of the ecosystem of FirecREST. The API doesn't provide these components, instead, it uses known standards in the industry while providing abstractions to support multiple techonologies.

![f7t_arch_complete](../../assets/img/arch_complete_infra.svg)

The dashed lines represents components that are optional, while the solid lines are mandatory for a proper use of FirecREST.

### (1) HPC Systems and workload manager and schedulers

Check out [here](./systems/README.md) how does FirecREST connect to the systems to execute commands and interact with the scheduler and filesystems.

### (2) Authentication/Authorization

Review how FirecREST enables access and fine-grained permissions [here](./auth/README.md).

### (3) Data Transfers

FirecREST handles data transfer up to 5 TB. See how this is done [here](./external_storage/README.md).

### (4) Health checks

Periodically FirecREST will [check](./health_checks/README.md) that the underlying infrastructure works as expected.
