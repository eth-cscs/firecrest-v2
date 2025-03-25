# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.3]

### Added

- New /status/liveness end-point (no auth is required)

### Changed


### Fixed

- Improved health checker reliability

## [2.2.2] - OPEN

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
- Images are now built for multiple platforms: inux/amd64, linux/arm64

### Fixed


## [2.1.4]

### Fixed

Helm Chart now allows to dynamically set volumes and annotations.


## [2.1.3]

### Added

Initial release.
