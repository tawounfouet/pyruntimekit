# PyRuntimeKit

PyRuntimeKit is an experimental Python runtime framework focused on reliable, explicit and progressively durable execution semantics.

> **Status:** pre-alpha. The current release milestone is `0.1.0a4 - Process & Subprocess Execution`. APIs may change throughout the `0.x` series.

## Why PyRuntimeKit?

PyRuntimeKit is designed around a small set of explicit runtime boundaries:

- domain semantics before infrastructure;
- a RuntimeKernel that owns lifecycle transitions;
- orchestration separated from execution mechanisms;
- adapters that depend on stable contracts rather than the reverse;
- local execution semantics proven before persistence or distributed coordination.

## Current release scope

`0.1.0a4 - Process & Subprocess Execution` expands the qualified execution
layer with five local mechanisms:

- synchronous `InlineExecutor`;
- asyncio Task-backed `AsyncExecutor`;
- thread-pool `ThreadExecutor`;
- child Python-process `ProcessExecutor`;
- explicit OS-command `SubprocessExecutor`.

This release extends the existing RuntimeKernel lifecycle authority and the
`ExecutionContext` contract with isolated process execution, explicit
Python-object serialization, bounded admission and observable capacity.

The root public API intentionally remains:

```python
from pyruntimekit import Runtime, RunHandle
```

`Runtime.submit()` remains synchronous and uses `InlineExecutor`.
Other concrete backends are imported from their dedicated modules. No public
`ProcessRuntime` or `SubprocessRuntime` is introduced.

The release does **not** claim hard cancellation, timeout/deadline guarantees,
durable Stores, sandboxing, remote/distributed execution, worker coordination,
recovery, checkpoints, leases or fencing.

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

```text
InlineExecutor
  direct / same process / same thread / shared memory

AsyncExecutor
  asyncio Task / same process / same thread / shared memory
  ContextVar propagation/isolation / bounded concurrency

ThreadExecutor
  ThreadPoolExecutor / worker thread / shared memory
  ContextVar propagation/isolation / bounded in-flight admission

ProcessExecutor
  ProcessPoolExecutor / isolated child process
  explicit stdlib pickle boundary / bounded in-flight admission

SubprocessExecutor
  create_subprocess_exec / isolated OS command process
  literal argv / stdout/stderr/exit code / bounded concurrency
```

The authority rule remains:

```text
RuntimeKernel = lifecycle authority
Runner        = application orchestration
Executor      = execution mechanism
RunHandle     = client reference
```

Concrete process and subprocess backends remain module-level imports:

```python
from pyruntimekit.executors.process import ProcessExecutor
from pyruntimekit.executors.subprocess import SubprocessExecutor
```

Both are **trusted-only** primitives. Process isolation does not mean a
security sandbox.

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

AsyncExecutor limits concurrently active Tasks with `max_concurrency`.
ThreadExecutor limits submitted/running pool Futures with `max_in_flight`,
independently of `max_workers`.

ProcessExecutor likewise exposes separate `max_workers` and
`max_in_flight`. Its capacity slot remains assigned until the actual
underlying pool Future completes, even if the caller cancels the await.

SubprocessExecutor bounds admitted child commands with
`max_concurrency`. Its capacity slot is retained until normal completion
or cancellation cleanup finishes.

These backends expose local `current_load`. Excess work waits before
entering the respective backend.

## Serialization and command boundaries

ProcessExecutor uses Python stdlib `pickle` (`HIGHEST_PROTOCOL`) to
preflight `ResolvedWorkload + ExecutionContext` in the parent, serialize
the result in the child and deserialize it in the parent. Failed input
serialization, failed result serialization and failed deserialization are
reported separately from ordinary workload exceptions. Lambdas/local
closures are not guaranteed to be picklable; untrusted pickle input is
not safe to load.

SubprocessExecutor executes explicit `argv` without invoking a shell.
It supports optional `cwd` and environment overlays and preserves
decoded `stdout`, `stderr` and `exit_code`. Non-zero exit codes and
launch exceptions are distinct normalized failures.

## Cancellation boundary

PyRuntimeKit deliberately does not claim hard termination guarantees.

For async Tasks, cancellation preserves `asyncio.CancelledError`.

For thread and process work:

```text
cancel caller await
!=
terminate running thread/child process
```

Their backend capacity remains allocated while the underlying Future
continues.

For subprocess commands, cancellation best-effort terminates the child
and waits for cleanup before releasing capacity. `close()` blocks new
commands but does not automatically terminate already-active ones.

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

AsyncExecutor, ThreadExecutor, ProcessExecutor and SubprocessExecutor are qualified execution backends. None is exposed as a separate public Runtime facade.

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
    │   ├── process.py
    │   ├── process_serialization.py
    │   ├── subprocess.py
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

The a4 milestone qualification report is:

`docs/releases/v0.1.0a4-qualification.md`

The isolated-backend conformance matrix is:

`tests/unit/executors/test_process_subprocess_conformance_a4.py`

The complete milestone gate is qualified with:

```text
705 tests passed
95.51% total coverage
Ruff lint passed
Ruff format passed
mypy strict passed
package build passed
typed wheel passed
clean-wheel smoke passed
```

Earlier a1, a2 and a3 qualification suites remain in the full CI run.

## Release notes

See `docs/releases/0.1.0a4.md`. Releases use GitHub prerelease assets
(wheel and source distribution). PyPI publication is not configured here.

## Contributing

See `CONTRIBUTING.md` for the development workflow and quality requirements.

## License

Apache-2.0.
