# ADR 0004 — Use controlled Run mutations with immutable snapshots

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

`Run` is the principal Aggregate Root and must evolve over its lifecycle while preserving identity, invariants and optimistic-concurrency semantics. The specifications recommend controlled aggregate mutations, immutable value objects and an explicit snapshot rather than a publicly mutable dataclass.

## Decision

`Run` is an Entity with stable `RunId` identity and read-only public properties. A newly created Run always starts in `CREATED` at `RunVersion(0)`.

`RunVersion` is an immutable, non-negative, monotone value object.

`RunSnapshot` is a separate immutable, schema-versioned, serialization-friendly representation used for persistence, comparison, recovery and audit. Snapshot timestamps use ISO-8601 UTC strings.

PR 05 deliberately does not add lifecycle transition methods. Transition rules and terminal-state enforcement remain the responsibility of the later state-machine/kernel lots. Snapshot restoration may restore any canonical `RunState` without replaying transitions.

## Consequences

- application code cannot assign `run.state` directly through the public API;
- future lifecycle operations will mutate the aggregate only through controlled methods/transition authority;
- persistence code can use `RunVersion` for compare-and-set semantics;
- snapshots remain distinct from transport DTOs and the live Entity;
- the current attempt is represented as an optional positive integer until `AttemptNumber` is introduced in Lot 05;
- metadata is validated as JSON-compatible and defensively immutable; a numeric size limit is deferred because the current specifications define no canonical bound.
