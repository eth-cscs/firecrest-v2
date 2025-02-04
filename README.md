## FirecREST-v2 Helm Charts

This is a repository for a Helm chart to deploy [FirecREST version 2](https://github.com/eth-cscs/firecrest-v2).

### Fetching the repository

```bash
helm repo add firecrest-v2 https://eth-cscs.github.io/firecrest-v2
helm repo update
```

The available versions can be listed with

```bash
helm search repo firecrest-v2/firecrest-api --versions
```

### Deploying the chart

```bash
helm install --create-namespace <deployment-name> -n <namespace> firecrest-v2/firecrest-api --values values.yaml
```
