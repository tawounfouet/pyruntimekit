# ADR 0001 — Use a `src/` layout

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

PyRuntimeKit needs packaging boundaries that prevent accidental imports from the repository root and exercise the installed package during development and tests.

## Decision

Use a `src/` layout with the import package located at `src/pyruntimekit/`.

## Alternatives

- Flat repository package layout.
- Namespace-package-first layout.

## Consequences

- Local tests exercise the same import shape as installed users.
- Package discovery is explicit.
- Development requires installing the project, typically in editable mode.
