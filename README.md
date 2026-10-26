# PyRuntimeKit

PyRuntimeKit is an experimental Python runtime framework focused on reliable, explicit and progressively durable execution semantics.

> **Status:** pre-alpha. The current release milestone is `0.1.0a2 — Runtime Kernel`. APIs may change throughout the `0.x` series.

## Why PyRuntimeKit?

PyRuntimeKit is designed around a small set of explicit runtime boundaries:

- domain semantics before infrastructure;
- a RuntimeKernel that owns lifecycle transitions;
- orchestration separated from execution mechanisms;
- adapters that depend on stable contracts rather than the reverse;
- local execution semantics proven before persistence or distributed coordination.

## Current release scope

`0.1.0a2 — Runtime Kernel` provides the first executable local vertical slice:

- `RuntimeKernel` command/decision authority;
- immutable attempt-scoped `ExecutionContext`;
- `SimpleRunner` orchestration;
- Executor contracts and `ResolvedWorkload`;
- deterministic in-process `InlineExecutor`;
- public synchronous `Runtime.submit()`;
- public `RunHandle` with `run_id`, `status()`, `result()` and `wait()`;
- normalized success/failure execution;
- package-wide qualification proving no hidden persistence or concurrency assumptions.

The qualified bootstrap is intentionally:

```text
same process
same thread
synchronous
in-memory
non-durable
```

It does **not** yet provide async/thread executors, durable stores, workers, cancellation, retry/recovery, checkpoints, effects, leases/fencing or distributed execution.

## Quickstart

```python
from pyruntimekit import Runtime
from pyruntimekit.domain import RunState

runtime = Runtime()

handle = runtime.submit(
    lambda context: {
        "run_id": context.run_id.value,
        "attempt": context.attempt.value,
    }
)

assert handle.status() is RunState.SUCCEEDED

result = handle.result()
print(result.value)
```

A submitted callable receives an `ExecutionContext`. In `0.1.0a2`, submission executes synchronously through `InlineExecutor`, so the returned handle already references a terminal Run.

## Execution model

The first public path is:

```text
Runtime.submit()
      ↓
SubmissionService
      ↓
RuntimeKernel
CREATED → ADMITTED → QUEUED
      ↓
SimpleRunner
      ↓
RuntimeKernel
RUNNING
      ↓
ExecutionContext
      ↓
InlineExecutor
      ↓
ExecutionResult
   /        \
success    failure
   ↓          ↓
SUCCEEDED   FAILED
      ↓
RunHandle
```

The central authority rule is:

```text
RuntimeKernel = lifecycle authority
Runner        = progression/orchestration
Executor      = execution mechanism
RunHandle     = client reference
```

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

```text
src/
└── pyruntimekit/
    ├── __init__.py
    ├── py.typed
    ├── api/
    │   ├── __init__.py
    │   ├── run_handle.py
    │   └── runtime.py
    ├── application/
    │   ├── __init__.py
    │   ├── runner.py
    │   └── submission.py
    ├── contexts/
    │   ├── __init__.py
    │   └── execution.py
    ├── domain/
    │   ├── attempt.py
    │   ├── enums.py
    │   ├── events.py
    │   ├── exceptions.py
    │   ├── failure.py
    │   ├── ids.py
    │   ├── invariants.py
    │   ├── result.py
    │   ├── run.py
    │   ├── validation.py
    │   └── workload.py
    ├── executors/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── capabilities.py
    │   └── inline.py
    └── kernel/
        ├── __init__.py
        ├── commands.py
        ├── decisions.py
        ├── errors.py
        ├── runtime_kernel.py
        └── transitions.py
```

## Architecture direction

The core dependency direction is:

```text
api → application → kernel → domain
```

Application code may depend on Executor contracts, while concrete executors remain independent from application and Kernel lifecycle semantics.

## Qualification

The detailed release qualification lives at:

`docs/qualification/0.1.0a2-runtime-kernel.md`

The milestone is qualified with 571 tests and a coverage gate above 95%.

## Contributing

See `CONTRIBUTING.md` for the development workflow and quality requirements.

## License

Apache-2.0.
