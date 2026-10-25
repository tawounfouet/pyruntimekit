"""Pure domain exceptions for invariant violations."""

from __future__ import annotations

from .enums import RunState


class DomainInvariantError(ValueError):
    """Base error for violations of PyRuntimeKit domain invariants."""


class InvalidRunTransitionError(DomainInvariantError):
    """Raised when a requested Run state transition is not allowed."""

    def __init__(self, current_state: RunState, next_state: RunState) -> None:
        self.current_state = current_state
        self.next_state = next_state
        super().__init__(f"invalid Run transition: {current_state.value} -> {next_state.value}")


__all__ = ["DomainInvariantError", "InvalidRunTransitionError"]
