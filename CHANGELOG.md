# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Initial repository bootstrap for the `0.1.0a1 — Domain Foundations` milestone.
- `src/` package layout and domain package boundary.
- Ruff, mypy, pytest, coverage and package-build baseline.
- GitHub Actions continuous integration workflow.
- Initial architecture decision records.
- Typed `RunId`, `WorkloadId`, `FailureId` and `EventId` domain identifiers.
- Canonical `RunState` enum with explicit stable string values and terminal-state classification.
- Backend-agnostic Workload model with durable references, descriptors and declarative resource hints.
