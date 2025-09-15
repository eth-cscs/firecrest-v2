# FirecREST-v2 Installation

## Kubernetes deployment

FirecREST repository includes a [Helm chart](https://github.com/eth-cscs/firecrest-v2/tree/master/build/helm/firecrest-api) to deploy FirecREST version 2 in a [Kubernetes](https://kubernetes.io/docs/concepts/overview/) cluster.

!!! note

    Follow this [link](https://helm.sh/docs/intro/quickstart/) to install Helm in your laptop.

### Fetching the repository

Download the official FirecREST helm repository to your local environment:

!!! example "Add FirecREST helm repository and update"

    ```bash
    $ helm repo add firecrest-v2 https://eth-cscs.github.io/firecrest-v2/charts/
    "firecrest-v2" has been added to your repositories
    ```

Update the local repository every time you deploy a new version:

!!! example "Update the latest versions"

    ```bash
    $ helm repo update
    (...)
    ...Successfully got an update from the "firecrest-v2" chart repository
    (...)
    ```

Available versions can be listed with `healm search`:

!!! example "List available versions"

    ```bash
    $ helm search repo firecrest-v2/firecrest-api --versions
    NAME                      	CHART VERSION	APP VERSION	DESCRIPTION
    firecrest-v2/firecrest-api	2.3.1        	2.3.1      	FirecREST APIs (version 2)
    firecrest-v2/firecrest-api	2.3.0        	2.3.0      	FirecREST APIs (version 2)
    firecrest-v2/firecrest-api	2.2.9        	2.2.9      	FirecREST APIs (version 2)
    firecrest-v2/firecrest-api	2.2.8        	2.2.8      	FirecREST APIs (version 2)
    firecrest-v2/firecrest-api	2.2.7        	2.2.7      	FirecREST APIs (version 2)
    firecrest-v2/firecrest-api	2.2.6        	2.2.6      	FirecREST APIs (version 2)
    firecrest-v2/firecrest-api	2.2.5        	2.2.5      	FirecREST APIs (version 2)
    ```

### Deploying FirecREST

Using `helm install`, you can easily deploy FirecREST-v2 in a Kubernetes `<namespace>`

!!! example "Deploy FirecREST-v2 using helm"

    ```bash
    $ helm install --create-namespace <deployment-name> -n <namespace> \ 
        firecrest-v2/firecrest-api --values values.yaml
    ```

## Values file

In the example above, you can use the public [values.yaml](https://github.com/eth-cscs/firecrest-v2/tree/master/build/helm/firecrest-api) as an example for deploying FirecREST.

!!! note
    A good practice would be to copy the `values.yaml` file, edit the copied file with the actual values to use in the local deployment, and use it in the `--values` option of `helm install` (ie, `helm install [...] --values /path/to/values-copy.yaml`)

There is a brief description of all the settings within the `values.yaml` file. However we recommend a more complete guide in our [configuration](../conf/README.md) section.

### Enabling *cluster-configs*

FirecREST supports the configuration of clusters using dedicated YAML files. This feature must be explicitly enabled in `values.yaml` with the following declaration:

!!! example "Configure FirecREST to get clusters configuration from a path"

    ```yaml
    firecrest:
    (...)
        clusters: path:/app/clusters
    ```
Once configured, FirecREST will search for cluster configuration files in the specified `clusters: path`  directory. To include these files in a Helm Chart deployment, one has to provide them via a `ConfigMap` named `firecrest-cluster-configs`.

The example below automatically loads all cluster's YAML files from the designated directory using a Helm template:

!!! example "Create a ConfigMap that loads cluster configuration from a path"

    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
    name: firecrest-cluster-configs
    data:
    {{- (.Files.Glob "clusters/**.yaml").AsConfig | indent 2 }}
    ```

To enable the Helm Chart to mount the ConfigMap, set the following value in `values.yaml`:

!!! example "Enabling cluster configuration from path"

    ```yaml
    (...)
    use_cluster_configs_path: true
    ```

### Templates

This setup only provides the pod deployment and service [templates](https://github.com/eth-cscs/firecrest-v2/tree/master/build/helm/firecrest-api/templates). This should be enough to run FirecREST as a standalone container with a functional TCP port to receive requests.