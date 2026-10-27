# ADR 0014 — AsyncExecutor creates one task and leaves cancellation semantics deferred

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

`0.1.0a3` introduces asynchronous execution after the synchronous local path was qualified and released in `0.1.0a2`.

The asynchronous backend must provide a real task boundary without taking ownership of Run lifecycle semantics, cancellation policy, timeout policy or capacity management before those features are designed.

## Decision

Introduce:

```text
pyruntimekit.executors.async_.AsyncExecutor
```

implementing:

```text
AsyncExecutorContract
```

and consuming:

```text
ResolvedAsyncWorkload
```

## Execution boundary

Each call to:

```python
await executor.execute(workload, context)
```

creates one explicit `asyncio.Task`.

Conceptually:

```text
caller task
   │
   ▼
AsyncExecutor.execute()
   │
   ▼
create_task(...)
   │
   ▼
resolved async workload
   │
   ▼
ExecutionResult
```

The backend remains in the same process and thread.

No thread pool, process or subprocess is introduced.

## Result normalization

If the awaited workload returns an existing `ExecutionResult`, the executor returns it unchanged.

Otherwise the value becomes:

```text
ExecutionResult.success(value=...)
```

## Exception normalization

Ordinary Python `Exception` values are normalized as:

```text
code     = EXECUTOR.ASYNC.EXCEPTION
category = EXECUTION
origin   = EXECUTOR
scope    = ATTEMPT
```

The Failure stores a safe cause summary and no raw traceback.

## Cancellation

`asyncio.CancelledError` is intentionally not converted into a workload Failure.

The executor catches:

```text
Exception
```

not:

```text
BaseException
```

This preserves cancellation as a control-flow signal.

However, this PR does not claim a cancellation capability. Runtime cancellation semantics belong to a later milestone.

Therefore:

```text
CancelledError propagation
≠
qualified cancellation semantics
```

## Capabilities

PR 22 declares exactly:

```text
IN_PROCESS
SHARED_MEMORY
TRUSTED_ONLY
ASYNC_EXECUTION
```

It does not yet declare:

```text
CONTEXTVARS_PROPAGATION
BOUNDED_CAPACITY
THREAD_EXECUTION
THREAD_CONTEXT_PROPAGATION
```

Context propagation and bounded capacity are qualified in later PRs.

## Architecture qualification evolution

The historical `0.1.0a2` qualification prohibited concurrency dependencies across the whole package because that release had no concurrent backend.

After `0.1.0a3` begins, that historical guarantee is frozen to the `0.1.0a2` surfaces.

Current executor architecture tests allow:

```text
asyncio
```

only inside:

```text
executors/async_.py
```

This prevents accidental concurrency leakage into Domain, Kernel, application or InlineExecutor.

## Non-goals

This PR does not add:

- AsyncRunner;
- public AsyncRuntime;
- ContextVar capability qualification;
- Semaphore capacity limits;
- queueing;
- cancellation requests;
- deadlines/timeouts;
- retry/recovery.

## Consequences

- PyRuntimeKit now has a real asynchronous execution mechanism;
- the synchronous `0.1.0a2` path remains unchanged;
- task creation is explicit and testable;
- cancellation signals are not misclassified as workload failures;
- capability declarations remain truthful;
- later PRs can add context propagation and bounded capacity without redesigning the executor contract.
