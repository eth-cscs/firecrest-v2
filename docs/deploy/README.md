# FirecREST-v2 Deployment


## FirecREST-v2 Helm Charts
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