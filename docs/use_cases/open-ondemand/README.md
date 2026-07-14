# Open OnDemand

[Open OnDemand](https://openondemand.org/) (OOD) is a web portal widely deployed at HPC centers, providing users with file management, interactive apps, and job submission through a browser. It connects to HPC systems through adapters in the [`ood_core`](https://github.com/OSC/ood_core) Ruby gem.

This use case describes a **proof-of-concept** FirecREST v2 adapter for `ood_core` that lets Open OnDemand communicate with HPC systems entirely via the FirecREST REST API — removing the need for direct SSH access or shared filesystem mounts between the OOD server and the cluster. It is a starting point and not ready for production use.

## Architecture

```
Browser → Apache/OOD → ood_core (FirecREST adapter) → FirecREST v2 API → HPC cluster
```

The adapter covers two areas of OOD functionality:

- **Job management** (`firecrest.rb`): submit, query, and cancel jobs via the `/compute` endpoints, implementing the standard `ood_core` adapter interface
- **File management** (`cluster_file.rb`): browse, upload, download, and edit files via the `/storage` endpoints, implementing the `ClusterFile` interface used by OOD's Files app

The adapter source files are included in this directory.

## Authentication

This is the key integration point between OOD and FirecREST. There are two models depending on how OOD is configured:

### Token passthrough (not implemented)

When OOD and FirecREST share the same OIDC provider, the user's access token obtained at login can be passed directly to FirecREST. Each request is then made under the authenticated user's own identity — no service account credentials need to be stored on the OOD server.

### Client credentials (implemented)

When OOD and FirecREST use different identity providers, a shared OAuth2 client (service account) can be configured. OOD holds a `client_id` and `client_secret` and exchanges them for a short-lived token on each request. In this model all users share the same identity toward FirecREST, which may not be suitable for all deployments.

The adapter reads the credentials from environment variables set in `nginx_stage.yml`:

```yaml title="/etc/ood/config/nginx_stage.yml"
pun_custom_env:
  FIRECREST_CLIENT_ID: "your-client-id"
  FIRECREST_CLIENT_SECRET: "your-client-secret"
  FIRECREST_TOKEN_URI: "https://auth.example.com/realms/firecrest/protocol/openid-connect/token"
```

In this model all users share the same identity toward FirecREST, which may not be suitable for all deployments.

## Cluster configuration

The adapter is registered in OOD by adding a cluster config file to `/etc/ood/config/clusters.d/`:

```yaml title="/etc/ood/config/clusters.d/my_cluster.yml"
my_cluster:
  metadata:
    title: "My HPC Cluster"
  login:
    host: "login.example.com"
  job:
    adapter: "firecrest"
    machine: "cluster_name"
    endpoint: "https://api.example.com/hpc/firecrest/v2"
```

The `machine` value must match the system name as registered in FirecREST.

## Files app integration

`ClusterFile` implements the interface expected by OOD's Files app, but two small additions to the OOD dashboard are needed to wire it up.

**Routing**: OOD's `FilesController#parse_path` needs a branch that detects FirecREST clusters and instantiates `ClusterFile` instead of the default `PosixFile` or `RemoteFile`. The routing key is the `fs` URL parameter: when it matches a cluster whose `job.adapter` is `firecrest`, the controller delegates all file operations to `ClusterFile`, which calls FirecREST under the hood.

```ruby
# In FilesController (dashboard app)
elsif firecrest_cluster?(filesystem)
  @path = OodAppkit.clusters[filesystem].job_adapter.cluster_file(normal_path)
  @filesystem = filesystem
```

**Sidebar link**: An initializer registers the remote filesystem in the Files sidebar so users can navigate to it. The path must be a valid mounted path on the cluster — FirecREST does not expose the root filesystem (`/`).

```ruby
# config/initializers/firecrest_files.rb
Rails.application.config.after_initialize do
  OodAppkit.clusters.select { |c| c.job_config[:adapter] == 'firecrest' }.each do |cluster|
    OodFilesApp.candidate_favorite_paths << FavoritePath.new(
      '/your/scratch/path',
      title: "#{cluster.title} Files",
      filesystem: cluster.id.to_s
    )
  end
end
```

Once these are in place, users see the cluster in the Files dropdown and can browse, upload, download, and edit files entirely through FirecREST — no shared filesystem mount required.

## Integration with `ood_core`

The adapter files (`firecrest.rb`, `cluster_file.rb`, `cluster_transfer.rb`) are intended to be added in the upstream to the [`ood_core`](https://github.com/OSC/ood_core) gem.

The gem version must satisfy `~> 0.24` (the constraint used by current OOD releases). The adapter has one external dependency — the [`jwt`](https://rubygems.org/gems/jwt) gem — which must be added to each OOD app's Gemfile that uses the adapter (typically `dashboard` and `myjobs`).

## Testing

The adapter ships with an integration test suite that runs against a real FirecREST installation without requiring a full OOD deployment. The tests cover connectivity, file operations (mkdir, upload, list, download, delete), job lifecycle (submit, query, cancel), and the `ClusterFile` interface.

Tests are skipped automatically if the required environment variables are not set, making them safe to include in CI pipelines that may not have access to a FirecREST installation.
