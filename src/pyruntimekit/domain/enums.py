"""Stable domain enumerations for PyRuntimeKit."""

from enum import StrEnum


class RunState(StrEnum):
    """Canonical lifecycle states of a Run."""

    CREATED = "CREATED"
    ADMITTED = "ADMITTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    SUSPENDED = "SUSPENDED"
    RECOVERING = "RECOVERING"
    LOST = "LOST"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    ABORTED = "ABORTED"

    @property
    def is_terminal(self) -> bool:
        """Return whether the state is terminal and cannot be left."""
        return self in _TERMINAL_RUN_STATES


_TERMINAL_RUN_STATES = frozenset(
    {
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.TIMED_OUT,
        RunState.ABORTED,
    }
)


__all__ = ["RunState"]
