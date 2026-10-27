# ADR 0021 - ProcessExecutor exposes an explicit pickle serialization boundary

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

ProcessExecutor executes Python callables in child processes through an owned `ProcessPoolExecutor`.

That backend necessarily transports:

```text
ResolvedWorkload
ExecutionContext
result / ExecutionResult
exceptions
```

across a process boundary.

Before this ADR, that serialization was an implementation fact of `ProcessPoolExecutor`, but not yet a PyRuntimeKit contract.

The `SERIALIZED_BOUNDARY` capability must therefore not be advertised until PyRuntimeKit can identify and normalize ordinary boundary failures explicitly.

## Decision

ProcessExecutor now exposes an explicit stdlib-pickle boundary.

The parent performs a preflight before submission:

```text
ResolvedWorkload + ExecutionContext
            |
            v
pickle.dumps(...)
            |
      +-----+-----+
      |           |
     ok         failure
      |           |
      v           v
 submit      INPUT_SERIALIZATION
```

The child explicitly serializes the successful workload outcome:

```text
workload.implementation(context)
            |
            v
pickle.dumps(result)
            |
      +-----+-----+
      |           |
     ok         failure
      |           |
      v           v
 bytes       RESULT_SERIALIZATION
```

The parent then explicitly deserializes those bytes:

```text
serialized result bytes
            |
            v
pickle.loads(...)
            |
      +-----+-----+
      |           |
     ok         failure
      |           |
      v           v
 outcome     RESULT_DESERIALIZATION
```

## Serializer

The milestone uses only the Python standard library:

```text
pickle
protocol = pickle.HIGHEST_PROTOCOL
```

No cloudpickle, dill or framework-specific serializer is introduced.

This intentionally means that arbitrary local functions, lambdas and closures are not promised to work.

The supported boundary is the set of values accepted by the configured Python runtime's stdlib pickle semantics.

## Input preflight

Before `ProcessPoolExecutor.submit()`, ProcessExecutor verifies that the tuple:

```text
(ResolvedWorkload, ExecutionContext)
```

can be pickled.

An ordinary incompatibility is normalized as:

```text
code     = EXECUTOR.PROCESS.INPUT_SERIALIZATION
category = EXECUTION
origin   = EXECUTOR
scope    = ATTEMPT
```

The Workload is not executed when this preflight fails.

## Child result serialization

After the callable returns successfully, the child explicitly serializes the outcome.

If that serialization fails, the child raises a transport-safe marker containing only:

- original exception type name;
- original exception message.

The parent normalizes that marker as:

```text
EXECUTOR.PROCESS.RESULT_SERIALIZATION
```

This avoids confusing an unpicklable result with an exception raised by the Workload itself.

## Parent result deserialization

The parent explicitly unpickles the serialized result bytes.

An ordinary deserialization failure is normalized as:

```text
EXECUTOR.PROCESS.RESULT_DESERIALIZATION
```

The Failure records the safe underlying exception summary.

## Ordinary workload exceptions

A callable exception remains distinct from serialization failure.

It continues to normalize as:

```text
EXECUTOR.PROCESS.EXCEPTION
```

Therefore the failure taxonomy now distinguishes:

```text
workload execution
input serialization
result serialization
result deserialization
```

## Existing ExecutionResult values

If the child outcome deserializes to an existing `ExecutionResult`, the parent preserves that object semantically rather than wrapping it in a second result.

## Capability promotion

After this ADR, ProcessExecutor may truthfully declare:

```text
TRUSTED_ONLY
PROCESS_EXECUTION
PROCESS_ISOLATION
SERIALIZED_BOUNDARY
```

It still does not declare:

```text
BOUNDED_CAPACITY
TIMEOUT
DEADLINE
```

Those guarantees remain separate concerns.

## SubprocessExecutor

SubprocessExecutor does not receive `SERIALIZED_BOUNDARY`.

Its OS command boundary is based on explicit argv/cwd/env and native process streams, not Python-object serialization.

## Compatibility and limits

The explicit preflight is designed to catch ordinary pickle incompatibilities before pool submission.

It does not claim:

- cross-Python-version wire compatibility;
- durable serialized payloads;
- stable storage format;
- remote transport compatibility;
- custom serializer negotiation;
- closure/lambda support;
- cloudpickle semantics.

The serialization boundary is local, ephemeral and tied to the active Python runtime.

## Architecture

Serialization helpers live in:

```text
pyruntimekit.executors.process_serialization
```

They remain an internal ProcessExecutor mechanism.

No serialization dependency enters Domain, Kernel, application orchestration or the root API.

## Non-goals

This ADR does not introduce:

- cloudpickle;
- dill;
- serializer plugin interfaces;
- persistent payload formats;
- remote execution;
- bounded submission;
- backpressure;
- timeout/deadline semantics;
- hard process cancellation;
- worker crash recovery.

## Consequences

- process transport failures are now first-class and diagnosable;
- unsupported callables fail before execution when detectable by preflight;
- successful child results cross an explicit byte boundary;
- unpicklable results cannot be mistaken for workload exceptions;
- `SERIALIZED_BOUNDARY` becomes a truthful ProcessExecutor capability;
- PR 33 can focus independently on capacity and cleanup semantics.
