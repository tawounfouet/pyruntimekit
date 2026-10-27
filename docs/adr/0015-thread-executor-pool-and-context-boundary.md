# ADR 0015 — ThreadExecutor uses an owned thread pool without context propagation guarantees

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

PyRuntimeKit `0.1.0a3` adds local concurrent execution after the synchronous Runtime Kernel slice and the first AsyncExecutor.

Blocking synchronous Workloads need a thread-backed execution mechanism, but the milestone deliberately separates:

- thread execution;
- ContextVar propagation;
- bounded submission/backpressure;
- cancellation semantics.

Those guarantees must not be conflated.

## Decision

Introduce:

```text
pyruntimekit.executors.thread.ThreadExecutor
```

backed by a dedicated:

```text
concurrent.futures.ThreadPoolExecutor
```

The backend consumes the existing synchronous:

```text
ResolvedWorkload
```

and exposes an awaitable execution method through:

```text
ThreadExecutorContract
```

Conceptually:

```text
async caller
   │
   ▼
ThreadExecutor.execute()
   │
   ▼
event_loop.run_in_executor(...)
   │
   ▼
ThreadPoolExecutor
   │
   ▼
sync workload
   │
   ▼
ExecutionResult
```

## Process and memory boundary

ThreadExecutor runs in:

```text
same process
shared memory
different thread
```

This is weak isolation, not a security sandbox.

## Pool ownership

Each ThreadExecutor owns its ThreadPoolExecutor.

The backend therefore exposes:

```python
close(wait=True, cancel_futures=False)
```

for explicit cleanup.

Calling `close()` multiple times is safe.

New execution after close is rejected.

Future Runtime composition may own this lifecycle centrally, but Runner does not.

## max_workers is not backpressure

`max_workers` limits concurrently active worker threads.

It does not bound the ThreadPoolExecutor submission queue.

Therefore:

```text
max_workers
≠
BOUNDED_CAPACITY
```

PR 23 does not claim `BOUNDED_CAPACITY`.

A later PR will introduce explicit bounded submission/backpressure.

## ContextVar boundary

The baseline ThreadExecutor intentionally does not call:

```python
contextvars.copy_context()
```

and does not claim:

```text
THREAD_CONTEXT_PROPAGATION
```

Context propagation and isolation across thread reuse are introduced and qualified separately in PR 24.

This separation makes the capability meaningful rather than incidental.

## Cancellation

Cancelling the coroutine awaiting a submitted thread operation may cancel the asyncio-side wait.

It does not portably terminate arbitrary Python code already running in the worker thread.

Therefore:

```text
cancel await
≠
kill running thread
```

PR 23 does not claim a cancellation capability.

## Result normalization

A plain synchronous return value becomes:

```text
ExecutionResult.success(value=...)
```

An existing ExecutionResult is returned unchanged.

Ordinary exceptions crossing the Future boundary become:

```text
code     = EXECUTOR.THREAD.EXCEPTION
category = EXECUTION
origin   = EXECUTOR
scope    = ATTEMPT
```

with safe cause summary and no raw traceback persistence.

## Capabilities

ThreadExecutor declares exactly:

```text
IN_PROCESS
SHARED_MEMORY
TRUSTED_ONLY
THREAD_EXECUTION
```

It does not yet declare:

```text
THREAD_CONTEXT_PROPAGATION
BOUNDED_CAPACITY
ASYNC_EXECUTION
```

The execute method is awaitable because completion is observed from an event loop; the workload itself remains synchronous.

## Architecture boundary

Concurrency-specific imports remain backend-scoped.

`thread.py` may depend on:

```text
asyncio
concurrent.futures
```

while Domain, Kernel, application and InlineExecutor remain independent from thread mechanics.

## Non-goals

This PR does not add:

- ContextVar propagation;
- bounded submission queues;
- cooperative cancellation token;
- hard thread termination;
- public ThreadRuntime;
- executor selection policy;
- timeout semantics.

## Consequences

- PyRuntimeKit can offload blocking synchronous Workloads without blocking the caller event loop;
- synchronous Workload contracts are reused;
- thread resource ownership is explicit;
- context propagation and backpressure remain separately testable capabilities;
- Kernel lifecycle authority remains unchanged.
