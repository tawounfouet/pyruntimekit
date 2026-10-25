# ADR 0003 — Use typed semantic identifiers

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

Runtime entities need stable identities that remain distinct by meaning. Using raw `str` values for every identifier would allow accidental substitution between concepts such as a Run, Workload, Failure or Event and would spread representation concerns through the domain.

## Decision

Use dedicated immutable identifier types for semantic identities.

The first set is:

- `RunId`;
- `WorkloadId`;
- `FailureId`;
- `EventId`.

Identifiers are UUID-backed internally, but the backing object is not part of the public domain contract. Construction and reconstruction use an opaque string value, and `.value` exposes a canonical serialization-friendly string.

The nil UUID is rejected. Two identifiers compare equal only when they have both the same semantic type and the same value.

## Alternatives

- raw `str` aliases;
- exposing `uuid.UUID` directly in domain APIs;
- ULID-based identifiers;
- prefixed opaque strings.

## Consequences

- identifier misuse is easier to catch through typing and equality semantics;
- identifiers are immutable, hashable and safe as mapping/set keys;
- persistent representations can use a stable string scalar;
- a future backing-format migration can be isolated behind the typed identifier contract;
- additional identifier types should be introduced only when their milestone requires them.
