# ADR 0016 — Context propagation is explicit per execution boundary

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

PyRuntimeKit passes an explicit immutable `ExecutionContext` across architectural boundaries, but Python applications also use ambient `ContextVar` values for tracing, correlation, tenancy and execution-local metadata.

The target context model states:

```text
explicit at architectural boundaries
ambient inside execution scope
```

Async task and thread boundaries have different propagation mechanics and must be qualified independently.

## Decision

Context propagation is captured at each call to an Executor.

The captured context belongs to that execution only.

## AsyncExecutor

Before invoking the resolved async implementation, AsyncExecutor performs:

```python
task_context = contextvars.copy_context()
```

Callable creation executes inside that copied context.

The explicit asyncio Task is then created with:

```python
asyncio.create_task(
    coroutine,
    context=task_context,
)
```

This avoids relying only on implicit event-loop behavior and makes the propagation contract visible in the backend.

AsyncExecutor now declares:

```text
CONTEXTVARS_PROPAGATION
```

in addition to its existing capabilities.

## Async isolation

Each call receives a fresh Context copy.

Therefore concurrent tasks may mutate their own ContextVar values without changing:

- the caller context;
- sibling tasks;
- future executions.

The qualification suite verifies concurrent isolation.

## ThreadExecutor

Before submission to the thread pool, ThreadExecutor performs:

```python
ambient_context = contextvars.copy_context()
```

The worker invokes the synchronous Workload through:

```python
ambient_context.run(workload.implementation, execution_context)
```

ThreadExecutor now declares:

```text
THREAD_CONTEXT_PROPAGATION
```

## Thread-pool reuse isolation

ThreadPoolExecutor may reuse the same worker thread across multiple executions.

A ContextVar mutated by one Workload must not become ambient state for the next Workload.

A fresh `copy_context()` per submission guarantees:

```text
submission A context
≠
submission B context
```

even when both happen on the same physical worker thread.

The copied Context is entered only for the duration of the Workload invocation and is restored afterward.

## Explicit ExecutionContext remains authoritative

ContextVar propagation does not replace the explicit ExecutionContext argument.

The architecture remains:

```text
ExecutionContext
=
explicit execution identity and immutable attempt-scoped data

ContextVar
=
ambient Python execution-scope state
```

The Executor always receives ExecutionContext explicitly.

## Capabilities

After this PR:

AsyncExecutor:

```text
IN_PROCESS
SHARED_MEMORY
TRUSTED_ONLY
ASYNC_EXECUTION
CONTEXTVARS_PROPAGATION
```

ThreadExecutor:

```text
IN_PROCESS
SHARED_MEMORY
TRUSTED_ONLY
THREAD_EXECUTION
THREAD_CONTEXT_PROPAGATION
```

Neither claims:

```text
BOUNDED_CAPACITY
```

until the backpressure PR qualifies it.

## Non-goals

This PR does not introduce:

- a public ambient `get_current_execution_context()` API;
- ExecutionScope abstraction;
- RuntimeContext;
- tracing backend;
- cancellation token propagation;
- deadline propagation;
- process/subprocess context envelopes;
- bounded capacity.

Those capabilities remain separate milestones.

## Consequences

- ambient Python context follows AsyncExecutor execution intentionally;
- thread boundaries no longer lose caller ContextVars;
- mutations are isolated from caller and sibling executions;
- thread reuse cannot leak workload ContextVars between submissions;
- capabilities now represent tested behavior rather than incidental implementation behavior.
