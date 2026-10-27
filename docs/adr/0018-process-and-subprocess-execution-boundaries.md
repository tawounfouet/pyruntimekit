# ADR 0018 - Process and subprocess execution use explicit boundaries

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

PyRuntimeKit 0.1.0a3 qualified three local execution mechanisms:

```text
InlineExecutor
AsyncExecutor
ThreadExecutor
```

All three execute inside the current Python process.

The next milestone introduces two different forms of process-based execution:

```text
Python workload
    -> child Python process

OS command
    -> external subprocess
```

Those are not the same abstraction.

A Python process backend may receive a resolved Python callable, subject to an explicit serialization boundary.

An OS subprocess backend executes a command and arguments. Treating that command as a Python callable would hide the actual execution model and make capability declarations misleading.

## Decision

### Process execution

Introduce:

```text
ProcessExecutorContract
```

as an awaitable structural contract consuming the existing synchronous:

```text
ResolvedWorkload
```

This preserves the semantic meaning:

```text
ResolvedWorkload
=
Python Workload + resolved synchronous callable
```

A future concrete ProcessExecutor must separately prove:

- child-process execution;
- process isolation;
- callable/context/result serialization;
- bounded process capacity;
- failure normalization;
- cleanup;
- cancellation truthfulness.

No concrete process backend is introduced by this ADR.

### Subprocess execution

Introduce an explicit command model:

```text
SubprocessCommand
    argv
    cwd
    env
```

and:

```text
ResolvedSubprocessWorkload
=
Domain Workload + explicit SubprocessCommand
```

Subprocess commands therefore do not masquerade as Python callables.

The first command boundary deliberately uses:

```text
argv: tuple[str, ...]
cwd: str | None
env: tuple[tuple[str, str], ...]
```

rather than a shell command string.

This keeps argument boundaries explicit and avoids making shell interpretation an implicit default.

A future concrete SubprocessExecutor must decide stdout/stderr capture, stdin, environment composition, exit-code normalization, cancellation and timeout semantics explicitly.

## Contracts

The new awaitable contracts are:

```text
ProcessExecutorContract
    execute(ResolvedWorkload, ExecutionContext)
        -> ExecutionResult

SubprocessExecutorContract
    execute(ResolvedSubprocessWorkload, ExecutionContext)
        -> ExecutionResult
```

They are separate from:

```text
Executor
AsyncExecutorContract
ThreadExecutorContract
```

No existing contract is widened or reinterpreted.

## Capability vocabulary

The capability vocabulary grows with:

```text
PROCESS_EXECUTION
SUBPROCESS_EXECUTION
PROCESS_ISOLATION
SERIALIZED_BOUNDARY
```

These are promises, not implementation hints.

Adding the values does not grant them to any existing Executor.

Therefore the qualified 0.1.0a3 capability sets remain unchanged.

## PROCESS_EXECUTION

Means that a backend executes a Python Workload in a child process rather than in the caller process.

It does not by itself guarantee:

- bounded capacity;
- timeout support;
- hard cancellation;
- durable execution;
- remote execution.

## SUBPROCESS_EXECUTION

Means that a backend starts an explicit OS subprocess command.

It does not mean that the subprocess is a Python Workload or that Python objects can cross its boundary.

## PROCESS_ISOLATION

Means that execution occurs in a separate OS process/address space.

It does not mean sandboxing, container isolation, privilege separation or security hardening.

## SERIALIZED_BOUNDARY

Means that Python-side values cross an execution boundary through serialization rather than shared memory.

A concrete ProcessExecutor may declare this capability only after the transport and failure semantics are implemented and qualified.

## Compatibility

The 0.1.0a3 slice remains intact:

- InlineExecutor capabilities unchanged;
- AsyncExecutor capabilities unchanged;
- ThreadExecutor capabilities unchanged;
- Runtime.submit() remains synchronous and InlineExecutor-backed;
- root package API remains Runtime, RunHandle and __version__;
- package version remains 0.1.0a3 during a4 development.

## Non-goals

This ADR does not introduce:

- ProcessExecutor implementation;
- SubprocessExecutor implementation;
- ProcessPoolExecutor;
- multiprocessing;
- subprocess execution;
- asyncio subprocess APIs;
- shell execution;
- stdin/stdout/stderr policy;
- timeout/deadline semantics;
- hard cancellation;
- sandboxing;
- durable execution;
- remote execution;
- distributed ownership.

## Consequences

- Python child-process execution and OS command execution have distinct contracts;
- future process serialization requirements are visible instead of implicit;
- shell semantics are not introduced accidentally;
- existing local Executor guarantees remain truthful;
- concrete process and subprocess backends can be implemented independently in later PRs.
