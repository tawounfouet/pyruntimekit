# ADR 0017 — Local Executor capacity is explicit and bounded

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

AsyncExecutor and ThreadExecutor can accept work faster than their local execution resources should consume it.

Without explicit admission control:

- AsyncExecutor can create arbitrarily many active Tasks;
- ThreadPoolExecutor has a finite worker count but an effectively unbounded internal submission queue.

The `0.1.0a3` qualification requires:

```text
bounded capacity
no hidden infinite queue
```

## Decision

Both local concurrent Executors own explicit capacity limits.

Capacity is acquired before backend execution starts and released only when the backend execution no longer consumes a slot.

## AsyncExecutor

AsyncExecutor accepts:

```python
max_concurrency: int = 100
```

and owns:

```python
asyncio.BoundedSemaphore(max_concurrency)
```

The semaphore is acquired before Task creation.

The slot covers the complete Task execution and is released in a `finally` block.

Therefore success, normalized failure and task cancellation all return capacity safely.

AsyncExecutor exposes:

```text
max_concurrency
current_load
```

where `current_load` counts executions that currently hold a backend slot.

## ThreadExecutor

ThreadExecutor accepts:

```python
max_in_flight: int = 32
```

independently from:

```python
max_workers
```

`max_workers` controls active worker threads.

`max_in_flight` controls the number of Workloads that may have been submitted to the ThreadPoolExecutor, including running and internally queued Futures.

Therefore:

```text
ThreadPool internal queue depth
<=
max_in_flight
```

up to the running workers included in that bound.

Excess callers wait on an external BoundedSemaphore before submission and do not enter the ThreadPoolExecutor queue.

## Cancellation and thread capacity

Cancelling the asyncio Task that awaits a ThreadExecutor result does not guarantee termination of a running Python thread.

Therefore its capacity slot must not be released merely because the await was cancelled.

The slot is tied to the underlying:

```text
concurrent.futures.Future
```

and released from that Future's completion callback.

This preserves the invariant:

```text
current_load
=
backend work still submitted/running
```

rather than:

```text
number of callers still awaiting
```

## Observable capacity

Both concurrent local Executors expose their configured bound and current load.

These values are local operational state, not Domain state and not Run lifecycle state.

They do not belong in RuntimeKernel.

## Capability declaration

After this qualification:

AsyncExecutor declares:

```text
IN_PROCESS
SHARED_MEMORY
TRUSTED_ONLY
ASYNC_EXECUTION
CONTEXTVARS_PROPAGATION
BOUNDED_CAPACITY
```

ThreadExecutor declares:

```text
IN_PROCESS
SHARED_MEMORY
TRUSTED_ONLY
THREAD_EXECUTION
THREAD_CONTEXT_PROPAGATION
BOUNDED_CAPACITY
```

## What BOUNDED_CAPACITY does not mean

It does not mean:

- the application cannot create many caller Tasks;
- global Runtime admission is implemented;
- Worker slots exist;
- priority queues exist;
- persistent queues exist;
- distributed backpressure exists.

It means only that the Executor does not submit or actively execute more backend work than its configured local capacity.

## Non-goals

This PR does not introduce:

- Runtime admission policy;
- queue priorities;
- Worker capacity;
- load balancing;
- executor registry selection;
- distributed queueing;
- cancellation tokens;
- timeouts.

## Consequences

- AsyncExecutor active execution is bounded;
- ThreadExecutor no longer feeds an unbounded hidden pool queue;
- cancellation cannot create phantom free thread capacity;
- capacity becomes observable and testable;
- later Worker/Runtime admission can build on truthful Executor capacity semantics.
