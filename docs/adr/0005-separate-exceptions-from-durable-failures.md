# ADR 0005 — Separate local exceptions from durable Failures

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

PyRuntimeKit must preserve the semantics of runtime incidents across process, persistence and backend boundaries. A live Python exception is a local mechanism and is not a durable domain contract.

## Decision

Represent runtime knowledge through an immutable, schema-versioned `Failure` model distinct from Python exceptions and from `RunState`.

`Failure` carries stable machine-readable classification (`FailureCode`, category, origin, severity and scope), retryability/recoverability hints, a UTC occurrence timestamp and JSON-compatible diagnostic payloads.

A `Failure` never contains a live Python exception or traceback object. A bounded non-recursive `FailureCauseSummary` may retain type/message context, and a `traceback_ref` may point to externally stored diagnostic material.

`str()` and `repr()` intentionally omit diagnostic payloads such as message, details, metadata, cause text and traceback references.

Retryability and recoverability are facts/hints for later policies; neither property performs a retry/recovery nor determines the terminal `RunState` by itself.

## Consequences

- future adapters/normalizers translate local exceptions into durable Failure contracts;
- policies consume machine-readable fields rather than parsing human messages;
- Failure serialization remains backend-neutral;
- redaction, recursive causal chains and exception normalizers can evolve separately in later milestones;
- Attempt failure evidence remains distinct from the terminal fate of a Run.
