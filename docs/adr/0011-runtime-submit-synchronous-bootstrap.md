# ADR 0011 — Runtime.submit assembles the first synchronous local vertical slice

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

PyRuntimeKit now has all internal building blocks required for one local execution:

```text
Domain
RuntimeKernel
ExecutionContext
SimpleRunner
Executor contract
InlineExecutor
```

The next milestone step is to expose a first public synchronous submission path without introducing background threads, async scheduling, persistence or the final RunHandle ahead of PR 18.

## Decision

Introduce:

```text
application/submission.py
api/runtime.py
```

`SubmissionService` owns use-case coordination:

```text
ResolvedWorkload
  ↓
CreateRun
  ↓
AdmitRun
  ↓
QueueRun
  ↓
SimpleRunner
  ↓
RUNNING
  ↓
InlineExecutor
  ↓
SUCCEEDED / FAILED
```

Every lifecycle change remains a RuntimeKernel decision.

## Runtime facade

`Runtime` is the public synchronous composition root for the bootstrap slice.

It wires:

```text
RuntimeKernel
+ SimpleRunner
+ InlineExecutor
+ SubmissionService
```

`Runtime.submit()` executes synchronously in the caller thread. No background worker or hidden async task is created.

## Accepted inputs

`Runtime.submit()` accepts:

- an already-created `ResolvedWorkload`;
- a synchronous Python callable with the initial contract `callable(ExecutionContext) -> object`.

A callable is adapted into:

```text
Workload(
  descriptor.kind = python.callable,
  descriptor.reference = module:qualname
)
+
ResolvedWorkload
```

This representation is explicitly local/ephemeral and does not imply durable reconstruction.

## Correlation

If the caller does not supply a correlation_id, the created RunId string becomes the correlation_id for the first attempt.

An explicit correlation_id continues to be normalized by ExecutionContext.

## Metadata

Bootstrap submission metadata is defensively copied into both:

- the Run metadata;
- the ExecutionContext metadata.

This is intentionally simple until SubmitOptions and richer context mapping exist.

## Transitional return type

PR 17 introduces internal/application `SubmissionOutcome` so the full synchronous slice can be inspected and qualified before RunHandle exists.

It preserves:

```text
CreateRun decision
AdmitRun decision
QueueRun decision
StartRun decision
terminal decision
RunnerOutcome
```

`SubmissionOutcome` is not re-exported from the package root and is not the intended stable public result of submit().

PR 18 will introduce `RunHandle` and replace the provisional return surface without changing SubmissionService orchestration.

## Public root

`Runtime` becomes the first high-level public symbol exported from:

```python
from pyruntimekit import Runtime
```

The package version remains `0.1.0a1` until the `0.1.0a2` release PR.

## Non-goals

- RunHandle implementation;
- Runtime.run convenience method;
- async Runtime;
- background execution;
- executor registry/selection;
- durable WorkloadRegistry;
- persistence;
- cancellation;
- retry/recovery.

## Consequences

- PyRuntimeKit now has a public executable path;
- the first vertical slice is synchronous and deterministic;
- public callable ergonomics exist without contaminating the Domain with live functions;
- PR 18 can focus purely on execution-reference semantics;
- later async/durable modes can evolve behind the same application boundaries.
