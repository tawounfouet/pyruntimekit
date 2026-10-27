# ADR 0019 - ProcessExecutor owns a local ProcessPoolExecutor boundary

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

ADR 0018 separated two different execution models:

```text
ResolvedWorkload
    -> ProcessExecutor

ResolvedSubprocessWorkload
    -> SubprocessExecutor
```

The first concrete `0.1.0a4` backend now needs to execute synchronous Python Workloads in child processes without moving Run lifecycle ownership out of RuntimeKernel.

The existing ThreadExecutor already established a useful local-backend pattern:

```text
Executor
    owns backend resource
    executes already-resolved Workload
    normalizes ordinary execution failures
    does not mutate Run lifecycle
```

Process execution adds a materially different memory and transport boundary.

## Decision

Introduce:

```text
pyruntimekit.executors.process.ProcessExecutor
```

implemented with an owned:

```text
concurrent.futures.ProcessPoolExecutor
```

The backend satisfies:

```text
ProcessExecutorContract
```

and consumes the existing synchronous:

```text
ResolvedWorkload
```

## Execution path

```text
caller asyncio Task
      |
      v
ProcessExecutor.execute()
      |
      v
ProcessPoolExecutor.submit()
      |
      v
child Python process
      |
      v
workload.implementation(ExecutionContext)
      |
      v
result / exception transported to parent
      |
      v
ExecutionResult normalization
```

The caller-facing API is awaitable so process-backed execution does not block the event loop while waiting for the child result.

## Initial capability declaration

The first ProcessExecutor implementation declares only:

```text
TRUSTED_ONLY
PROCESS_EXECUTION
PROCESS_ISOLATION
```

It deliberately does not yet declare:

```text
SERIALIZED_BOUNDARY
BOUNDED_CAPACITY
```

### Why TRUSTED_ONLY?

A separate OS process is an isolation boundary, not a security sandbox.

The child code can still perform arbitrary operations allowed to the current user and environment.

Therefore:

```text
PROCESS_ISOLATION
!=
SANDBOX
```

and submitted Python code must still be trusted.

### Why not SERIALIZED_BOUNDARY yet?

`ProcessPoolExecutor` necessarily transports Workload, context, results and exceptions between processes.

However this PR does not yet define or qualify the public serialization contract:

- supported callable shapes;
- supported context/result payloads;
- preflight behavior;
- serialization-specific failure taxonomy;
- portability across process start methods.

Those semantics belong to PR 32.

Until then the implementation may use the underlying pool transport without advertising `SERIALIZED_BOUNDARY` as a stable capability promise.

### Why not BOUNDED_CAPACITY yet?

`max_workers` bounds active child processes but does not prevent callers from submitting more Futures than workers.

Therefore it is not equivalent to the previously qualified:

```text
BOUNDED_CAPACITY
```

promise.

Explicit process submission capacity and backpressure belong to PR 33.

## Failure normalization

Ordinary exceptions observed by the parent are normalized to:

```text
code     = EXECUTOR.PROCESS.EXCEPTION
category = EXECUTION
origin   = EXECUTOR
scope    = ATTEMPT
```

The Failure stores:

- safe exception type;
- safe exception message;
- executor identity;
- workload kind.

No raw traceback reference is persisted.

This initial code covers both child workload exceptions and pool/transport exceptions until the serialization boundary receives its dedicated semantics.

## Result normalization

If the child returns a normal value:

```text
value
    -> ExecutionResult.success(value=value)
```

If the child already returns an `ExecutionResult`, the parent preserves it rather than wrapping it again.

## Context

The exact `ExecutionContext` supplied to `execute()` is passed across the child-process boundary with the Workload.

The Executor validates before submission that:

```text
ResolvedWorkload.workload_id
==
ExecutionContext.workload_id
```

Process-specific ambient ContextVar propagation is not claimed.

## Cleanup

ProcessExecutor owns its process pool.

It exposes:

```text
close(wait=True, cancel_futures=False)
```

with idempotent semantics.

Once closed, new executions are rejected.

Pool lifetime therefore remains explicit rather than depending on interpreter shutdown.

## Cancellation

Cancelling the caller's asyncio await is not defined as hard child-process termination.

This PR does not introduce a hard cancellation capability or claim.

Detailed cancellation, capacity retention and process termination semantics remain deferred.

## Architecture boundary

Concrete process primitives are confined to:

```text
pyruntimekit.executors.process
```

Domain, Kernel and application orchestration remain unaware of `ProcessPoolExecutor`.

The root package API is not expanded.

Users of this pre-release backend import it explicitly from its backend module.

## Non-goals

This ADR does not introduce:

- Process serialization preflight;
- stable serialization compatibility rules;
- bounded process submission;
- process backpressure;
- timeout/deadline semantics;
- hard process cancellation;
- worker crash recovery;
- SubprocessExecutor;
- shell execution;
- sandboxing;
- durable execution;
- Runtime.submit() process selection;
- public ProcessRuntime.

## Consequences

- PyRuntimeKit now has its first real child-process execution backend;
- child-process isolation is observable and testable;
- process execution remains separate from OS subprocess commands;
- ProcessExecutor does not overclaim serialization or capacity guarantees;
- resource ownership remains explicit;
- later PRs can harden serialization, capacity and conformance independently.
