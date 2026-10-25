# ADR 0006 — Keep lifecycle laws in Domain and transition authority in Kernel

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

`0.1.0a1` must formalize the official Run lifecycle before the RuntimeKernel exists. The lifecycle specification is normative and defines allowed transitions, terminal-state protection and several cross-object invariants.

## Decision

Store the canonical transition matrix and pure reusable validators in `domain/invariants.py`.

The Domain answers questions such as:

- is `current_state -> next_state` allowed?
- does a retry preserve `RunId`?
- does the next Attempt advance exactly one number?
- is `finished_at` coherent with terminality?
- is terminal success/failure evidence coherent?

The Domain does **not** apply transitions, persist state, resolve races, emit events automatically or invoke policies.

`RuntimeKernel` in `0.1.0a2` will become the transition authority that combines these laws with guards, policies, persistence/version checks and event production.

## Error strategy

`DomainInvariantError` is the compact base taxonomy for pure invariant violations.

`InvalidRunTransitionError` specializes the common state-transition rejection case and retains both current and requested states.

Public API errors such as `RunStateError` remain a separate API concern and may translate domain/kernel errors later.

## Consequences

- the lifecycle source of truth exists before Kernel implementation;
- all 13 Run states are covered by one explicit transition table;
- terminal states have no outgoing transitions;
- adapters and Executors have no authority to modify lifecycle state;
- future Kernel code can reuse pure validators without duplicating rules;
- invariants involving concepts not yet modeled (deadlines, effects, leases) remain specified but are not prematurely implemented.
