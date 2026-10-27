# ADR 0022 - Process and subprocess executors use explicit bounded capacity

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

PyRuntimeKit already qualified bounded capacity for AsyncExecutor and ThreadExecutor.

The process-oriented backends introduced in 0.1.0a4 initially did not claim the same guarantee.

A `ProcessPoolExecutor(max_workers=N)` bounds active workers, but it does not bound the number of Futures admitted to its internal queue.

Likewise, independently launching OS subprocesses without an admission bound allows callers to create an unbounded number of concurrent child processes.

Therefore:

```text
worker count
!=
admission capacity
```

and process isolation by itself does not provide backpressure.

## Decision

ProcessExecutor and SubprocessExecutor gain explicit local admission capacity.

Both backends may now truthfully advertise:

```text
BOUNDED_CAPACITY
```

## ProcessExecutor

ProcessExecutor gains:

```text
max_in_flight
current_load
```

with a bounded semaphore in front of `ProcessPoolExecutor.submit()`.

The execution path becomes:

```text
caller
  |
  v
serialization preflight
  |
  v
acquire capacity
  |
  v
ProcessPoolExecutor.submit()
  |
  v
backend Future
  |
  v
actual backend completion
  |
  v
release capacity
```

### max_workers versus max_in_flight

`max_workers` controls how many worker processes may execute concurrently.

`max_in_flight` controls how many process executions may be admitted into the backend, whether running or queued inside the pool.

For example:

```text
max_workers   = 2
max_in_flight = 8
```

means at most two child workers execute at once while at most eight submitted process executions may occupy backend capacity.

Additional callers wait before pool submission.

## Process cancellation

Cancelling the asyncio Task that awaits a ProcessExecutor result does not imply hard termination of an already-running child process.

Therefore the capacity slot belongs to the backend Future, not to the caller await.

```text
caller await cancelled
        |
        v
backend Future still running
        |
        v
current_load unchanged
        |
        v
backend Future completes
        |
        v
slot released
```

If the underlying Future is cancelled before it begins execution, its completion callback releases capacity normally.

This preserves truthful backpressure and avoids admitting replacement work while the original backend work is still consuming process resources.

## Process close

ProcessExecutor continues to own its ProcessPoolExecutor and exposes idempotent:

```text
close(wait=True, cancel_futures=False)
```

Closing rejects new executions.

A caller already waiting for admission re-checks the closed state after it acquires a slot and rejects execution without submitting to the pool.

## SubprocessExecutor

SubprocessExecutor gains:

```text
max_concurrency
current_load
```

A bounded semaphore is acquired before creating an OS process.

```text
caller
  |
  v
acquire capacity
  |
  v
create_subprocess_exec
  |
  v
communicate / cancellation cleanup
  |
  v
release capacity
```

The slot covers the full active command lifecycle.

## Subprocess cancellation

When the awaiting Task is cancelled after a subprocess has started:

1. the child receives best-effort termination;
2. PyRuntimeKit waits for process cleanup;
3. `CancelledError` is re-raised;
4. only then is the capacity slot released.

Thus a replacement command cannot consume the slot while the cancelled child is still being cleaned up.

This remains a cleanup guarantee, not a hard-cancellation capability.

## Subprocess close

SubprocessExecutor now exposes idempotent:

```text
close()
```

The operation marks the executor closed and rejects new commands.

It deliberately does not terminate commands already active.

Existing executions retain their capacity slot and continue according to their normal completion or cancellation semantics.

A future lifecycle API may add explicit draining or mass termination, but this milestone does not imply either behavior.

## Observable load

For both backends:

```text
current_load
```

counts executions currently holding a capacity slot.

It is intentionally local in-memory state.

It is not:

- durable accounting;
- distributed worker load;
- operating-system process count;
- queue depth outside the Executor;
- a scheduling metric across machines.

## Capabilities

After this ADR:

### ProcessExecutor

```text
TRUSTED_ONLY
PROCESS_EXECUTION
PROCESS_ISOLATION
SERIALIZED_BOUNDARY
BOUNDED_CAPACITY
```

### SubprocessExecutor

```text
TRUSTED_ONLY
SUBPROCESS_EXECUTION
PROCESS_ISOLATION
BOUNDED_CAPACITY
```

SubprocessExecutor still does not claim `SERIALIZED_BOUNDARY`.

## Non-goals

This ADR does not introduce:

- timeout or deadline semantics;
- hard ProcessPool child termination;
- kill-all-on-close behavior;
- process-group management;
- signal routing APIs;
- durable admission queues;
- distributed capacity;
- worker leases;
- remote execution;
- public runtime backend selection.

## Consequences

- process pool queue growth is explicitly bounded;
- subprocess fan-out is explicitly bounded;
- local load becomes observable;
- caller cancellation cannot prematurely free process capacity;
- subprocess cancellation retains capacity through cleanup;
- close semantics are explicit and idempotent;
- PR 34 can now define a common conformance matrix over the two isolated-execution backends.
