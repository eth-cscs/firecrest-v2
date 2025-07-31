# FirecREST-v2 Deployment


## Helm Charts
This repository includes a Helm chart to deploy FirecREST version 2.

### Fetching the repository

```
helm repo add firecrest-v2 https://eth-cscs.github.io/firecrest-v2/charts/
helm repo update
```

The available versions can be listed with
```
helm search repo firecrest-v2/firecrest-api --versions
```

Deploying the chart
```
helm install --create-namespace <deployment-name> -n <namespace> firecrest-v2/firecrest-api --values values.yaml
```

## Values file

### Enabling <i>cluster-configs</i>

FirecREST supports the configuration of clusters using dedicated YAML files. This feature must be explicitly enabled in `firecrest-config.yaml` with the following declaration:
```
clusters: path:/app/clusters
```
Once configured, FirecREST will search for cluster configuration files in the specified "clusters" directory. To include these files in a Helm Chart deployment, one has to provide them via a ConfigMap named `firecrest-cluster-configs`.
The example below automatically loads all YAML files from the designated directory using a Helm template:
```
apiVersion: v1
kind: ConfigMap
metadata:
  name: firecrest-cluster-configs
data:
  {{- (.Files.Glob "clusters/**.yaml").AsConfig | nindent 2 }}
```
To enable the Helm Chart to mount the ConfigMap, set the following value in `values.yaml`:
```
use_cluster_configs_path: true
```