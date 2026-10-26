# ADR 0010 — InlineExecutor executes ResolvedWorkload in-process

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

`0.1.0a2` already has RuntimeKernel, ExecutionContext and SimpleRunner. The first executable vertical slice still needs a concrete backend without introducing async, threads, processes, serialization or durability.

The Domain Workload is intentionally declarative. Its descriptor explains what should be executed and how it may be reconstructed; it must not embed a live Python callable.

## Decision

Introduce `pyruntimekit.executors` with:

- `Executor` Protocol;
- `ResolvedWorkload`;
- `ExecutorDescriptor`;
- `ExecutorCapabilities`;
- `InlineExecutor`.

`ResolvedWorkload` pairs a declarative Domain Workload with a live callable that has already been resolved:

```text
Workload
+
callable(context)
=
ResolvedWorkload
```

This preserves the boundary:

```text
Domain Workload = execution intent / stable descriptor
ResolvedWorkload = process-local executable representation
```

## Inline execution

`InlineExecutor` invokes the resolved callable exactly once in the current process and current thread.

It creates no task, thread, process or subprocess and performs no serialization.

## Capabilities

The initial capability set is exactly:

```text
IN_PROCESS
SHARED_MEMORY
TRUSTED_ONLY
```

Absence of a capability is meaningful. InlineExecutor does not claim hard cancellation, process isolation, remote execution or durability.

## Result normalization

If the callable returns an existing `ExecutionResult`, InlineExecutor returns it unchanged.

Otherwise the returned Python value becomes:

```text
ExecutionResult.success(value=...)
```

## Exception normalization

Ordinary Python `Exception` instances are converted into a normalized `Failure` with:

```text
code     = EXECUTOR.INLINE.EXCEPTION
category = EXECUTION
origin   = EXECUTOR
scope    = ATTEMPT
```

The Failure stores a safe non-recursive cause summary and no raw traceback. `BaseException` values outside `Exception` are not swallowed.

## Runner integration

`SimpleRunner` now consumes the stable `Executor` contract and a `ResolvedWorkload` rather than a raw declarative Workload.

The application layer imports `pyruntimekit.executors.base`, never the concrete `InlineExecutor` module.

## Non-goals

- durable workload resolution;
- WorkloadRegistry;
- async execution;
- thread/process/subprocess execution;
- hard cancellation;
- persistence;
- retry semantics;
- Run lifecycle ownership.

## Consequences

- PyRuntimeKit now has a concrete deterministic backend;
- Domain remains free of live callable objects;
- custom Executors can target the same stable boundary;
- Runtime.submit() can next adapt a user callable into a Workload + ResolvedWorkload and compose the first public execution path.
