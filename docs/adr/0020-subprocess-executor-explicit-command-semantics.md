# ADR 0020 - SubprocessExecutor uses explicit exec-style command semantics

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

PyRuntimeKit 0.1.0a4 separates Python child-process execution from OS command execution.

```text
ResolvedWorkload
    -> ProcessExecutor

ResolvedSubprocessWorkload
    -> SubprocessExecutor
```

The subprocess backend must make command boundaries explicit and must not silently introduce shell interpretation.

## Decision

Introduce:

```text
pyruntimekit.executors.subprocess.SubprocessExecutor
```

implemented with:

```text
asyncio.create_subprocess_exec
```

The executor consumes:

```text
ResolvedSubprocessWorkload
    workload
    command.argv
    command.cwd
    command.env
```

No shell command string is accepted by the backend.

## Command execution

```text
SubprocessCommand.argv
      |
      v
create_subprocess_exec(*argv)
      |
      v
external OS process
      |
      +--> stdout
      +--> stderr
      +--> exit code
      |
      v
ExecutionResult
```

Argument boundaries are preserved exactly.

Shell interpolation, command substitution, glob expansion and shell pipelines are therefore not implicit runtime behavior.

## Environment

`SubprocessCommand.env` is interpreted as an explicit overlay on the current process environment.

```text
parent environment
      +
command.env
      =
child environment
```

This preserves normal executable discovery and platform environment while allowing Workload-specific overrides.

## Working directory

If `cwd` is provided, it is passed directly to the subprocess creation API.

No directory mutation occurs in the parent process.

## Output model

stdout and stderr are captured as bytes and decoded as UTF-8 with replacement for invalid byte sequences.

The resulting strings are stored directly on `ExecutionResult`.

## Exit semantics

### Exit code 0

```text
exit_code == 0
    -> ExecutionResult.success
```

The successful result carries:

- `exit_code`;
- `stdout`;
- `stderr`.

### Non-zero exit code

A non-zero exit code is normalized as:

```text
code     = EXECUTOR.SUBPROCESS.NONZERO_EXIT
category = EXECUTION
origin   = EXECUTOR
scope    = ATTEMPT
```

The failed result still preserves:

- exact exit code;
- captured stdout;
- captured stderr.

This allows callers to reason about both normalized runtime failure semantics and native process diagnostics.

## Launch/runtime exceptions

Exceptions raised while starting or communicating with the subprocess are normalized as:

```text
EXECUTOR.SUBPROCESS.EXCEPTION
```

The Failure includes a safe cause summary and no raw traceback reference.

## Capabilities

The initial backend declares only:

```text
TRUSTED_ONLY
SUBPROCESS_EXECUTION
PROCESS_ISOLATION
```

It does not declare:

```text
SERIALIZED_BOUNDARY
BOUNDED_CAPACITY
TIMEOUT
DEADLINE
```

An external process boundary is not equivalent to a security sandbox.

## Cancellation

If the awaiting asyncio Task is cancelled after the child starts, the executor performs best-effort termination and waits for process cleanup before re-raising `CancelledError`.

This cleanup behavior is not advertised as a hard cancellation capability.

## Architecture

The concrete subprocess primitive is confined to:

```text
pyruntimekit.executors.subprocess
```

RuntimeKernel remains Run lifecycle authority.

The public root package API remains unchanged.

## Non-goals

This ADR does not introduce:

- shell execution;
- stdin streaming;
- timeout/deadline policy;
- bounded subprocess capacity;
- backpressure;
- process-group management;
- signal policy;
- sandboxing;
- durable execution;
- public SubprocessRuntime;
- Runtime.submit() backend selection.

## Consequences

- OS commands no longer masquerade as Python callables;
- argv semantics are explicit and shell-free;
- native stdout/stderr/exit-code diagnostics are preserved;
- non-zero exit is normalized consistently into the Failure model;
- the backend can later receive bounded-capacity and conformance hardening independently.
