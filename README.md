# PyRuntimeKit

PyRuntimeKit is an experimental Python runtime framework focused on reliable, explicit and progressively durable execution semantics.

> **Status:** pre-alpha. The current release milestone is `0.1.0a3 — Async & Thread Execution`. APIs may change throughout the `0.x` series.

## Why PyRuntimeKit?

PyRuntimeKit is designed around a small set of explicit runtime boundaries:

- domain semantics before infrastructure;
- a RuntimeKernel that owns lifecycle transitions;
- orchestration separated from execution mechanisms;
- adapters that depend on stable contracts rather than the reverse;
- local execution semantics proven before persistence or distributed coordination.

## Current release scope

`0.1.0a3 — Async & Thread Execution` extends the qualified Runtime Kernel with three local execution mechanisms:

- deterministic direct `InlineExecutor`;
- explicit Task-based `AsyncExecutor`;
- thread-backed `ThreadExecutor`.

The release provides:

- `RuntimeKernel` command/decision lifecycle authority;
- immutable attempt-scoped `ExecutionContext`;
- `SimpleRunner` orchestration;
- synchronous and asynchronous resolved workload contracts;
- explicit Executor capability declarations;
- `InlineExecutor`, `AsyncExecutor` and `ThreadExecutor`;
- ContextVar propagation and isolation;
- bounded async concurrency;
- bounded thread in-flight submission;
- local backpressure;
- normalized success/failure execution;
- truthful async/thread cancellation boundaries;
- explicit ThreadExecutor pool cleanup;
- standardized Executor conformance and transverse milestone qualification.

The root public API intentionally remains:

```python
from pyruntimekit import Runtime, RunHandle
```

`Runtime.submit()` remains synchronous and continues to execute through InlineExecutor.

The release does **not** yet provide ProcessExecutor, SubprocessExecutor, timeout/deadline policy, durable stores, workers, retry/recovery, checkpoints, leases/fencing or distributed execution.

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

A submitted callable receives an `ExecutionContext`. The public Runtime path remains synchronous, so the returned handle already references a terminal Run.

## Local Executor model

The qualified execution mechanisms are:

```text
InlineExecutor
  direct
  same process
  same thread
  shared memory

AsyncExecutor
  asyncio Task
  same process
  same thread
  shared memory
  ContextVar propagation/isolation
  bounded active concurrency

ThreadExecutor
  ThreadPoolExecutor
  same process
  worker thread
  shared memory
  ContextVar propagation/isolation
  bounded in-flight submission
  explicit pool cleanup
```

The central authority rule remains:

```text
RuntimeKernel = lifecycle authority
Runner        = progression/orchestration
Executor      = execution mechanism
RunHandle     = client reference
```

Concurrent Executors extend execution mechanics only. They do not own Run lifecycle state transitions.

## Context propagation

AsyncExecutor creates each execution with an explicit copied context:

```text
caller Context
      ↓
copy_context()
      ↓
asyncio Task
      ↓
async Workload
```

ThreadExecutor similarly propagates an explicit copied context into the worker thread:

```text
caller Context
      ↓
copy_context()
      ↓
ThreadPool submission
      ↓
worker thread
```

Concurrent async executions and reused thread workers are qualified against context leakage.

## Capacity and backpressure

AsyncExecutor uses a bounded semaphore around active execution:

```text
max_concurrency
      ↓
BoundedSemaphore
      ↓
Task creation/execution
```

ThreadExecutor bounds submitted/running backend work separately from its worker count:

```text
max_in_flight
      ↓
capacity gate
      ↓
ThreadPoolExecutor submission
```

Excess work waits before entering the execution backend.

## Cancellation boundary

The release deliberately avoids claiming impossible cancellation guarantees.

Async cancellation preserves `asyncio.CancelledError` as control flow and releases local capacity.

For thread execution:

```text
cancel await
!=
terminate Python thread
```

If an await is cancelled while its underlying thread keeps running, the capacity slot remains held until the backend Future completes.

## Public Runtime execution model

The current public path remains:

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

AsyncExecutor and ThreadExecutor are qualified execution backends, but they are not yet exposed as separate public AsyncRuntime/ThreadRuntime facades.

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
    │   ├── async_.py
    │   ├── base.py
    │   ├── capabilities.py
    │   ├── inline.py
    │   └── thread.py
    └── kernel/
        ├── __init__.py
        ├── commands.py
        ├── decisions.py
        ├── errors.py
        ├── runtime_kernel.py
        └── transitions.py
```

## Architecture direction

The core dependency direction remains:

```text
api → application → kernel → domain
```

Application code may depend on stable Executor contracts, while concrete Executors remain independent from application and Kernel lifecycle semantics.

The Domain remains infrastructure-independent.

## Qualification

The detailed milestone qualification lives at:

`docs/qualification/0.1.0a3-async-thread-execution.md`

The standardized Executor conformance record lives at:

`docs/qualification/0.1.0a3-executor-conformance.md`

The complete milestone gate is qualified with:

```text
637 tests
95.61% total coverage
Ruff lint passed
Ruff format passed
mypy strict passed
package build passed
typed wheel passed
clean-wheel smoke passed
```

## Release notes

See:

`docs/releases/0.1.0a3.md`

## Contributing

See `CONTRIBUTING.md` for the development workflow and quality requirements.

## License

Apache-2.0.
