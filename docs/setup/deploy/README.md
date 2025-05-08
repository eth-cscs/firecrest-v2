# The `firecrestv2` Helm chart

Firecrest can be deployed with the `firecrestv2/firecrest` Helm chart:

```bash
helm repo add firecrestv2 http://repo-url
helm repo update
helm install <release> firecrestv2/firecrest  -n <namespace> -f values.yaml
```

In addition to the `firecrestv2/firecrest` chart, several other charts are available to help you deploy a full "demo environment" for trying out FirecREST, including all necessary components:

```bash
$> helm search repo firecrestv2
NAME                 	CHART VERSION	APP VERSION                 	DESCRIPTION
firecrestv2/firecrest	2.2.1        	2.2.1                       	A Helm chart for deploying FirecREST
firecrestv2/keycloak 	1.0.0        	26.0.7                      	A Helm chart for deploying a Keycloak identity ...
firecrestv2/minio    	1.0.0        	RELEASE.2022-10-24T18-35-07Z	A Helm chart for deploying a MinIO object stora...
firecrestv2/secrets  	1.0.0        	1.0.0                       	A Helm chart for deploying a Secret to provide ...
firecrestv2/slurm    	1.0.0        	24.11.3                     	A Helm chart for deploying a Slurm cluster in a...
```

More info about this can be found in the section Demo environment.

## The `values.yaml` file

The chart can be customize through its `values.yaml` file. This file contains all the parameters needed to configure the deployment, behavior, and integration of FirecREST within your Kubernetes cluster. It includes settings for scaling, container images, authentication, external services, clusters, and storage backends. In the following sections, we briefly describe the structure of the `values.yaml` file and how to adjust it to fit different environments.

At the top of `values.yaml`, you define basic deployment settings for FirecREST:

- `replicas`: Number of pod replicas to deploy.
    
- `image`: Container image for FirecREST.
    
- `apiUrl`: Public URL where FirecREST will be accessible.
    
- `loggingLevel`: Log verbosity (`INFO`, `DEBUG`, etc.).
    
- `environment`: Deployment environment (e.g., `production`).
    

You can also add Kubernetes annotations:

- `deploymentAnnotations` apply to the Deployment resource (e.g., enabling Prometheus scraping).
    
- `podAnnotations` apply to pods (e.g., configuring Istio sidecar behavior).
    

These options allow you to customize the FirecREST deployment for your cluster.

### Certificates

The `certificates` section in the `values.yaml` file configures HTTPS certificates for the JupyterHub instance using Let's Encrypt. Under `certificates.letsencrypt.urls`, you can specify a list of domain names for which automatic certificates will be requested. Optionally, alternative challenge types, like `letsencrypt-http01`, can be configured for different validation methods. This ensures that connections to the deployed JupyterHub instance are securely encrypted.

### Vault

The `vault` section in the `values.yaml` file configures integration with a HashiCorp Vault service for securely managing secrets. When `vault.enabled` is set to `true`, the application will retrieve sensitive information (such as API keys or credentials) directly from Vault. You must provide the Vault `url`, specify the `secretEngine` used for storing secrets, and set authentication parameters like `roleId` and `secretPath`. This setup helps avoid hardcoding secrets into the deployment configuration, improving security.

### Volumes

The Helm chart supports, to some extent, scenarios where additional files need to be made available to FirecREST.
A common example is providing custom certificates for an external gateway.

To include such files, you’ll need to download the chart’s source and place them in the `files` directory.
Once added, these files can be referenced in the `volumes.configmap` section of `values.yaml`.

For example, suppose you've added `files/file1.txt` and `files/file2.txt`.
You can then define the following in your `values.yaml`:

```yaml
volumes:
  configmap:
    enabled: true
    name: files-extra
    items:
    - key: files1
      path: files1.txt
    - key: files2
      path: files2.txt
```

This configuration will mount the specified files into the FirecREST pod at `/app/config/extra/`.

Similarly, **sensitive files** such as SSH private keys, passphrases, or API credentials should be managed via Kubernetes Secrets.  
You can configure these in the `volumes.secret` section of `values.yaml`. For example:

```yaml
volumes:
  secret:
    enabled: true
    name: firecrest-secrets
    items:
    - key: ssh_private_key_firesrv
      path: ssh_private_key_firesrv
    - key: ssh_passphrase_firesrv
      path: ssh_passphrase_firesrv
```

These secrets will also be mounted under `/app/config/extra/` in the pod and will be accessible to FirecREST at runtime.

### Configuration

The config section organizes the main FirecREST application settings. Here you can specify the base API path, authentication mechanisms, and optional documentation servers. It also defines the SSH credentials that FirecREST uses to connect to remote systems, and lists the HPC clusters it manages, including their SSH access, schedulers, and file systems. Finally, the storage subsection configures the S3-compatible object storage used for data staging and transfers. Together, these parameters allow you to customize how FirecREST interacts with external services, compute clusters, and storage backends. For a detailed explanation of each configuration option, refer to the [FirecREST configuration documentation](https://eth-cscs.github.io/firecrest-v2/setup/conf/).


## Deploying FirecREST with the demo environment

As mentioned earlier, the demo environment includes several services that FirecREST depends on, such as authentication, storage, and workload management.

To deploy the demo environment, begin by installing the necessary subcharts that provide these services. These include:

- **Keycloak**: for authentication and identity management.
    
- **MinIO**: as an S3-compatible storage backend.
    
- **Slurm**: the Slurm cluster that FirecREST will target.
    
The `firecrestv2/secrets` chart is used to deploy a Kubernetes Secret containing user SSH keys.
These keys are mounted into the pod where FirecREST runs, allowing it to authenticate with the underlying HPC system.

In a production environment, SSH keys should be managed more securely—either through an external SSH key server or by using any preferred method to make the keys available on the cluster’s filesystem.
This allows greater flexibility and integration with existing security practices.

Make sure all the deployments are dene within a same Kubernetes namespace (in this example, `fcv2-demo`).
If it doesn’t exist yet, it will be created with the first command.

```bash
helm install keycloak  firecrestv2/keycloak -nfcv2-demo -f values-keycloak.yaml --create-namespace
helm install minio     firecrestv2/minio    -nfcv2-demo -f values-minio.yaml
helm install slurm     firecrestv2/slurm    -nfcv2-demo
helm install secrets   firecrestv2/secrets  -nfcv2-demo
```

the values files are 

* `values-keycloak.yaml`
```yaml
keycloak:
  url: keycloak-helm.iram-tds.tds.cscs.ch
```

* `values-minio.yaml`
```yaml
host: minio-demov2.iram-tds.tds.cscs.ch
```

Once these components are deployed, FirecREST itself can be installed

```bash
helm install firecrest firecrestv2/firecrest -nfcv2-demo -f values-firecrest.yaml
```

At this point, all the core services should be up and running.

You can verify the deployment by checking the status of the pods in the namespace:

```bash
kubectl get pods -n fcv2-demo
```


```bash
helm delete keycloak  -nfcv2-demo
helm delete minio     -nfcv2-demo
helm delete slurm     -nfcv2-demo
helm delete secrets   -nfcv2-demo
helm delete firecrest -nfcv2-demo
```
