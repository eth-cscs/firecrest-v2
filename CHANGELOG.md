# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0] - OPEN

### Added

- Add support for the OpenPBS scheduler.

### Changed

### Fixed

## [2.2.8]

### Added

- Refactor FastAPI models for Slurm, in order to make it easier to add new schedulers.
- Make cp recursive so that directories can also be copied and add the option to keep symbolic links.

### Changed

### Fixed

- Fixed Slurm timestamps parsing issues, timezone was not properly handled.

## [2.2.7]

### Added

- Query parameter `allusers` in `GET /compute/jobs` to show all visible jobs for the user in the scheduler
- Environment variable `UVICORN_LOG_CONFIG` to enable [Uvicorn log configuration](https://www.uvicorn.org/settings/#logging) file path (analog to `--log-config`)

### Changed

### Fixed

- Show nodes from hidden partitions using SLURM CLI
- Fixed reservation start and end datatime parsing.
- Handles instances where no Job exit status is provided.
- Fixed unnecessary user keys retrieval with SSH connection pool.
- Fixed proper SSH process termination on timeout.
- `UVICORN_LOG_CONFIG` value on helm chart

## [2.2.6]

### Added

- `account` optional parameter to job submission request
- `script_path` optional parameter for submitting jobs from a remote file
- JupyterHub example
- Documentation for logging architecture
- Workflow orchestrator example
- UI browser app example
- POST and PUT bodies request examples
- Documentation and examples in C# .NET

### Changed

- Documentation for logging architecture
- Images for documentation
- Description of API definition

### Fixed

## [2.2.5]

### Added
- Log for request and command execution tracing

### Changed

### Fixed

- Fix health check for older versions of Slurm REST API (< v0.0.42)

## [2.2.4]

### Added

### Changed

- Slurm health check now uses "scontrol ping"

### Fixed

- Disabled cluster health checks won't cause errors
- Github pages changed to allow mkdocs syntax for notes and code samples

## [2.2.3]

### Added

- New /status/liveness end-point (no auth is required)

### Changed


### Fixed

- Improved health checker reliability
- Fixed Demo launcher when no public certificate is provided

## [2.2.2]

### Added

### Changed

### Fixed

- Demo launcher ssh login node checks socket connection instead executing a ping
- Removed deprecated keycloak configuration from docker dev environment

## [2.2.1]

### Added
- FirecREST Web UI has been added to the demo image.

### Changed

### Fixed

- Templates for upload and download using `filesystems/transfer` endpoint.
- Return error code 408 when basic commands timeout on the cluster.

## [2.2.0]

### Added

- Added `/filesystem/{system_name}/transfer/compress` and `/filesystem/{system_name}/transfer/extract`
  - `compress` operations (on `transfer` and `ops` endpoints) accept `match_pattern` parameter to compress files using `regex` syntax.
- Added new FirecREST demo image.
- Added support for private key passphrase.
### Changed
- Images are now built for multiple platforms: linux/amd64, linux/arm64

### Fixed


## [2.1.4]

### Fixed

Helm Chart now allows to dynamically set volumes and annotations.


## [2.1.3]

### Added

Initial release.
