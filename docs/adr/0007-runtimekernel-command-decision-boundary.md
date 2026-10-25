# ADR 0007 — RuntimeKernel owns lifecycle commands and returns atomic decisions

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

`0.1.0a1` deliberately stopped at pure lifecycle laws. The domain defines the canonical Run transition matrix and reusable invariants, but no component applies those transitions.

`0.1.0a2` needs one explicit authority before Runner, Executor, persistence or public Runtime APIs are introduced.

## Decision

Introduce `pyruntimekit.kernel.RuntimeKernel` as the sole runtime-layer authority that interprets lifecycle commands.

The initial contract is:

```text
Command
   +
current Run
   │
   ▼
RuntimeKernel
   │
   ▼
KernelDecision
├── resulting Run
├── emitted Domain Events
└── optional final RunResult
```

Run creation is handled separately:

```text
CreateRun
→ RuntimeKernel.create()
→ CREATED Run(version=0) + RunCreated(version=0)
```

Every accepted lifecycle transition:

1. validates against the canonical domain transition matrix;
2. produces a new Run representation rather than mutating the caller's object;
3. increments `RunVersion` exactly once;
4. updates `updated_at` monotonically;
5. emits a Domain Event carrying the resulting aggregate version;
6. returns all logical facts together in one immutable `KernelDecision`.

## Controlled Run evolution

`Run` exposes no public transition API.

A package-internal `_evolve_lifecycle()` primitive applies already-validated facts while preserving Run identity. It deliberately does not decide whether a transition is legal.

This keeps the dependency of responsibilities explicit:

```text
domain/invariants.py
→ defines lifecycle laws

kernel/transitions.py
→ validates and applies requested transitions

RuntimeKernel
→ interprets commands and produces decisions/events
```

## Attempt rule

Transition into `RUNNING` requires the next exact `AttemptNumber`:

```text
None → 1
N    → N+1
```

Other transitions cannot change `current_attempt`.

## Terminal evidence

`CompleteRun` requires a successful `RunResult`.

`FailRun` requires a normalized `Failure`; the Kernel creates the corresponding failed `RunResult`.

The final result is carried by `KernelDecision` rather than embedded into the current `RunSnapshot`. This avoids prematurely coupling the persistence-neutral Run snapshot to arbitrary generic result values.

A later persistence/UoW milestone must persist the logical boundary coherently:

```text
Run transition
+
final result/failure evidence
+
Domain Events
```

## Time semantics

Commands carry explicit timezone-aware logical timestamps.

The Kernel does not read wall-clock time itself in this milestone. A future Clock contract can provide those timestamps at application/runtime boundaries.

## Non-goals

RuntimeKernel does not:

- execute Workloads;
- select Executors;
- access a database;
- publish events externally;
- perform network or filesystem I/O;
- spawn threads/processes;
- sleep;
- implement retry/admission policy.

## Consequences

- Runner and Executors cannot invent Run semantics;
- terminal-state protection remains centralized;
- event ordering follows aggregate version ordering;
- Kernel tests remain deterministic;
- the first vertical execution slice can be built on top of a stable transition authority;
- persistence remains a later adapter/application concern.
