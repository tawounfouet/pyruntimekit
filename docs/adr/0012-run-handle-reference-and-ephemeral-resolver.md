# ADR 0012 — RunHandle is a read reference over an explicit ephemeral registry

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

`Runtime.submit()` now completes one local execution synchronously. The public API still needs to return a `RunHandle` instead of leaking the internal `SubmissionOutcome`.

The target API requires that a RunHandle be a client reference to execution, not ownership of a live Run.

Persistence and RunStore abstractions belong to later milestones and must not be implied by this bootstrap.

## Decision

Introduce public generic `RunHandle[T]` with the initial surface:

```text
run_id
status()
result()
wait()
```

The handle stores only:

```text
RunId
+
read resolver
```

It does not contain:

- a live `Run`;
- a `SubmissionOutcome`;
- a `RunnerOutcome`;
- an Executor;
- a RuntimeKernel;
- execution ownership.

## Bootstrap read resolver

The synchronous Runtime owns an explicit `_InMemoryRunHandleResolver`.

After a synchronous submission completes, the Runtime records only:

```text
RunId
terminal RunState
RunResult
```

The resolver deliberately does not retain the live Run aggregate.

## Non-durability

The bootstrap resolver is:

```text
in-memory
process-local
ephemeral
non-durable
```

It is not a `RunStore` and must not be presented as persistence.

Restarting the process loses this read model.

Future store-backed resolvers can satisfy the same RunHandle read boundary without changing handle ownership.

## status()

`status()` returns the latest RunState visible through the resolver.

For `0.1.0a2`, Runtime.submit() is synchronous, so a returned handle always references a terminal Run.

## result()

`result()` returns the terminal RunResult already available through the resolver.

## wait()

`wait()` delegates directly to `result()` in the synchronous bootstrap.

It performs no:

- sleep;
- polling;
- thread blocking loop;
- hidden async bridge.

Later asynchronous or durable runtimes may provide explicit waiting semantics while preserving RunHandle as a client reference.

## Deferred surface

The following remain deferred:

- `cancel()` until cancellation request semantics exist;
- `refresh()` until external state can change independently;
- `events()` until event persistence/query exists;
- timeout/poll_interval waiting options;
- durable resolver/store integration.

## Public API

The root package now intentionally exports:

```python
from pyruntimekit import Runtime, RunHandle
```

`Runtime.submit()` returns a RunHandle instead of SubmissionOutcome.

`SubmissionOutcome` remains an internal application orchestration artifact for qualification.

## Consequences

- the public API now matches the intended submit/handle shape;
- RunHandle cannot mutate or own execution;
- no persistence assumption is hidden;
- PR 19 can qualify public success/failure/status/result behavior end to end;
- future stores can replace the ephemeral resolver behind the handle boundary.
