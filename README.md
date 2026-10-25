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

## Current release scope

`0.1.0a1 — Domain Foundations` provides the qualified domain foundation for PyRuntimeKit:

- typed identifiers and immutable value objects;
- Workload contracts;
- Run aggregate, version and snapshots;
- Attempt lifecycle primitives;
- normalized durable Failure contracts;
- backend-neutral ExecutionResult / RunResult and ArtifactRef;
- versioned Run domain events;
- canonical Run lifecycle transition matrix and pure invariants;
- architecture tests enforcing an infrastructure-independent domain boundary.

The release intentionally does **not** provide RuntimeKernel, executors, persistence, workers, leases, checkpoints, effects, recovery or external framework integrations yet.

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

## Current repository layout

    src/
    └── pyruntimekit/
        ├── __init__.py
        ├── py.typed
        └── domain/
            ├── attempt.py
            ├── enums.py
            ├── events.py
            ├── exceptions.py
            ├── failure.py
            ├── ids.py
            ├── invariants.py
            ├── result.py
            ├── run.py
            ├── validation.py
            └── workload.py

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
