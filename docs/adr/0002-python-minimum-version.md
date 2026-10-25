# ADR 0002 — Require Python 3.12 or newer

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

PyRuntimeKit will rely on modern typing and concurrency semantics. The bootstrap should establish one minimum Python baseline before public contracts start to accumulate.

## Decision

Set the minimum supported Python version to Python 3.12.

## Alternatives

- Python 3.11 for a wider compatibility window.
- Supporting multiple older Python lines from the first alpha.

## Consequences

- The codebase can use a modern standard-library and typing baseline.
- CI can remain intentionally small during early alpha development.
- Supporting older Python versions later would require an explicit compatibility decision.
