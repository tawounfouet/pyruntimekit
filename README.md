# PyRuntimeKit

PyRuntimeKit is an experimental Python runtime framework focused on reliable, explicit and progressively durable execution semantics.

> **Status:** pre-alpha. The current implementation milestone is `0.1.0a1 — Domain Foundations`. APIs may change throughout the `0.x` series.

## Why PyRuntimeKit?

PyRuntimeKit is designed around a small set of explicit runtime boundaries:

- domain semantics before infrastructure;
- a RuntimeKernel that owns lifecycle transitions;
- orchestration separated from execution mechanisms;
- adapters that depend on stable contracts rather than the reverse;
- local execution semantics proven before persistence or distributed coordination.

## Current bootstrap scope

The repository currently establishes the package, quality tooling and CI baseline required to implement the domain layer. It intentionally does **not** implement executors, stores, workers, leases, checkpoints, effects, recovery or external framework integrations yet.

## Development setup

    python -m venv .venv
    source .venv/bin/activate
    python -m pip install -e ".[dev]"

Run the quality gate:

    ruff check .
    ruff format --check .
    mypy src tests
    pytest --cov=pyruntimekit --cov-report=term-missing
    python -m build

## Initial repository layout

    src/
    └── pyruntimekit/
        ├── __init__.py
        └── domain/
            └── __init__.py

    tests/
    └── unit/
        └── domain/

    docs/
    ├── specs/
    └── adr/

## Architecture direction

The core dependency direction is intended to evolve as:

    api → application → kernel → domain

The domain package must remain independent from persistence, execution backends and higher-level frameworks.

## Contributing

See `CONTRIBUTING.md` for the development workflow and quality requirements.

## License

Apache-2.0.
