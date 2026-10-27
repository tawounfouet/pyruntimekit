# ADR 0023 - Isolated executor conformance is capability-driven

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

PyRuntimeKit 0.1.0a4 introduces two isolated execution backends with different transport models:

```text
ProcessExecutor
    -> Python callable
    -> child Python process
    -> serialized object boundary

SubprocessExecutor
    -> explicit argv
    -> external OS process
    -> stdout/stderr/exit-code boundary
```

The backends share important execution guarantees but they must not be forced into identical semantics where the underlying models differ.

A conformance suite therefore needs to distinguish:

```text
shared guarantees
vs
backend-specific guarantees
```

## Decision

Define isolated-executor conformance as a capability-driven matrix.

## Shared guarantees

Both ProcessExecutor and SubprocessExecutor must satisfy:

```text
awaitable execution contract
explicit descriptor identity
TRUSTED_ONLY
PROCESS_ISOLATION
BOUNDED_CAPACITY
not IN_PROCESS
not SHARED_MEMORY
Workload / ExecutionContext identity validation
normalized ExecutionResult success/failure
observable bounded load
explicit cleanup
idempotent close
rejection after close
narrow root API
```

These guarantees are backend-neutral within the isolated-execution family.

## ProcessExecutor differential guarantees

ProcessExecutor additionally conforms to:

```text
PROCESS_EXECUTION
SERIALIZED_BOUNDARY
Python callable execution
child PID differs from caller PID
explicit serialization failure taxonomy
caller cancellation does not imply child termination
```

The serialization boundary is part of ProcessExecutor conformance because Python objects cross the process boundary.

## SubprocessExecutor differential guarantees

SubprocessExecutor additionally conforms to:

```text
SUBPROCESS_EXECUTION
literal argv semantics
no implicit shell
stdout preservation
stderr preservation
exit-code preservation
non-zero exit normalization
cancellation cleanup before capacity release
```

SubprocessExecutor explicitly does not conform to `SERIALIZED_BOUNDARY` because its contract is not Python-object transport.

## Capability truthfulness

Conformance tests validate declared capabilities, not inferred implementation details.

A backend must not receive a capability merely because the underlying library happens to expose related behavior.

For example:

```text
ProcessPoolExecutor max_workers
!=
BOUNDED_CAPACITY
```

until explicit admission control exists.

Likewise:

```text
OS process boundary
!=
SERIALIZED_BOUNDARY
```

for SubprocessExecutor.

## Result normalization

Both backends must return `ExecutionResult` values to callers.

However the native diagnostics differ:

### ProcessExecutor

```text
Python value / ExecutionResult
or normalized Failure
```

### SubprocessExecutor

```text
exit_code
stdout
stderr
plus normalized Failure when appropriate
```

Conformance checks the shared result envelope while preserving these backend-specific diagnostics.

## Cleanup

Conformance requires explicit cleanup behavior appropriate to backend ownership.

ProcessExecutor owns a process pool and must close it explicitly.

SubprocessExecutor owns no persistent process pool but still has an explicit closed state that rejects new work.

The conformance contract does not require both backends to implement identical close signatures.

## Cancellation

Cancellation semantics remain capability-specific rather than normalized into a false common promise.

ProcessExecutor:

```text
cancelled await
!=
hard child termination
```

SubprocessExecutor:

```text
cancelled await
-> best-effort terminate child
-> wait cleanup
-> release capacity
-> re-raise CancelledError
```

The conformance suite verifies truthfulness rather than enforcing one cancellation mechanism.

## Root API

Concrete ProcessExecutor and SubprocessExecutor remain explicit backend-module imports.

The root package continues to expose only the intentionally stable public runtime API.

Conformance therefore verifies that isolated backends do not silently widen:

```text
pyruntimekit
```

or the concrete-backend surface of:

```text
pyruntimekit.executors
```

## Relationship to milestone qualification

PR 34 establishes reusable conformance expectations.

PR 35 performs milestone-level qualification across:

- compatibility with prior milestones;
- architecture boundaries;
- isolated execution behavior;
- serialization;
- capacity;
- cancellation;
- cleanup;
- public API stability.

Therefore:

```text
PR 34 = backend conformance contract
PR 35 = milestone qualification
```

## Non-goals

This ADR does not introduce:

- new Executor capabilities;
- timeout/deadline semantics;
- common hard-cancellation semantics;
- remote execution;
- durable execution;
- serializer plugins;
- runtime backend selection;
- root API expansion.

## Consequences

- ProcessExecutor and SubprocessExecutor can be compared without erasing their differences;
- capability declarations become executable conformance criteria;
- future isolated backends can reuse the same shared guarantees;
- PR 35 can qualify the milestone against a stable conformance baseline.
