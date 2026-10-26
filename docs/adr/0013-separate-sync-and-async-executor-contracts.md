# ADR 0013 — Separate synchronous and asynchronous Executor contracts

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

`0.1.0a2` introduced a deliberately synchronous local execution slice:

```text
ResolvedWorkload
→ Executor
→ InlineExecutor
→ ExecutionResult
```

The next milestone adds AsyncExecutor and ThreadExecutor.

A single ambiguous callable contract such as:

```text
Callable[[ExecutionContext], object]
```

cannot safely represent both synchronous and asynchronous implementations because an awaitable is also an object. If the existing InlineExecutor received an async implementation accidentally, it could treat the coroutine object itself as a successful value.

The current synchronous path is already qualified and must remain source-compatible.

## Decision

Keep the existing synchronous contracts:

```text
ResolvedWorkload
Executor
```

and introduce explicit asynchronous counterparts:

```text
ResolvedAsyncWorkload
AsyncExecutorContract
```

The resolved callable types are distinct:

```text
ResolvedCallable
=
Callable[[ExecutionContext], object]

ResolvedAsyncCallable
=
Callable[[ExecutionContext], Awaitable[object]]
```

The distinction is primarily a typed contract. Construction validates that the implementation is callable without executing user code merely to prove awaitability.

## Why not convert Executor to async immediately?

Doing so would break the already-qualified synchronous contract consumed by SimpleRunner and InlineExecutor.

`0.1.0a3` should add concurrency capabilities incrementally rather than forcing the entire public Runtime path through an async abstraction before AsyncRuntime semantics are designed.

Therefore:

```text
Executor
=
synchronous contract retained for compatibility

AsyncExecutorContract
=
awaitable backend contract
```

A later milestone may unify or generalize these contracts if a public async Runtime requires it, but that migration must be explicit.

## Capability vocabulary

The capability vocabulary is expanded with:

```text
ASYNC_EXECUTION
THREAD_EXECUTION
CONTEXTVARS_PROPAGATION
THREAD_CONTEXT_PROPAGATION
BOUNDED_CAPACITY
```

Capabilities remain promises, not implementation hints.

Adding enum values does not grant them to existing executors.

InlineExecutor therefore remains exactly:

```text
IN_PROCESS
SHARED_MEMORY
TRUSTED_ONLY
```

## Thread execution

ThreadExecutor will continue to consume the synchronous `ResolvedWorkload` because it offloads blocking synchronous work to a thread.

Its future capabilities may include:

```text
IN_PROCESS
SHARED_MEMORY
TRUSTED_ONLY
THREAD_EXECUTION
THREAD_CONTEXT_PROPAGATION
BOUNDED_CAPACITY
```

only after those behaviors are implemented and qualified.

## Async execution

AsyncExecutor will consume `ResolvedAsyncWorkload` and satisfy `AsyncExecutorContract`.

Its capabilities will be declared only when the corresponding behavior exists, including contextvars propagation and bounded concurrency.

## Non-goals

This ADR does not introduce:

- AsyncExecutor implementation;
- ThreadExecutor implementation;
- asyncio tasks;
- thread pools;
- context propagation machinery;
- capacity management;
- cancellation;
- timeout semantics;
- public AsyncRuntime API.

Those belong to subsequent PRs in `0.1.0a3`.

## Consequences

- the `0.1.0a2` synchronous slice remains source-compatible;
- InlineExecutor cannot be silently reclassified as async;
- AsyncExecutor receives an explicit awaitable workload contract;
- ThreadExecutor can reuse the synchronous workload contract;
- capability growth remains truthful and testable;
- future concurrency mechanics stay outside Domain and Kernel.
