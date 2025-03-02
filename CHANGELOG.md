# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.1]

### Added

- Added log tracing of SSH commands, filesystem and scheduler interactions with standard JSON format.
- Added f7tlog for debugging and general usage


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
