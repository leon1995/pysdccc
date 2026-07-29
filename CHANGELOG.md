# Changelog

All notable changes to the pysdccc module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note:** This file is no longer maintained by hand. Release notes are now
> generated automatically from merged pull requests and published on the
> [GitHub Releases](https://github.com/Draegerwerk/pysdccc/releases) page.
> The entries below are kept as a historical record.

## [Unreleased]

## [1.1.0] - 2026-03-10

### Added

- `install` function that accepts both remote URLs and local zip file paths
- `extract_zip_file` async function in `_download` module
- `is_remote_path` utility function to distinguish URLs from local file paths
- CLI `install` command now accepts local zip file paths in addition to URLs
- exported `install` and `extract_zip_file` from the public API
- added macos pipeline to CI

### Changed

- replaced pyright with [ty](https://github.com/astral-sh/ty) for type checking
- switched build backend from hatchling to uv (`uv_build`)
- CLI `install` argument renamed from `url` to `path` to reflect local path support
- `build_command` return `Sequence[str]` instead of `list[str]`
- refactored CLI `download` to only download (returns temp file path); extraction is now a separate step
- replaced synchronous `zipfile` extraction in async `download` with async `extract_zip_file`
- fixed sync README example to call `.result()` on `Future` return values

## [1.0.0] - 2025-08-18

### Added

- capture logs of the SDCcc subprocess
- added a deprecation warning to all sync functions (except in `_cli.py`)

### Changed

- Remove some of the duplicated code by running async code with anyio
- replaced sync methods of `download` and `is_downloaded` with async functions and added a `_sync` extension to the end of the sync functions
- updated dependencies. most notable is increasing the `junitparser>=4`

## [0.1.0] - 2025-05-16

### Added

- initial code
