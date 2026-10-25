"""Stable domain enumerations for PyRuntimeKit."""

from enum import IntEnum, StrEnum


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


class IsolationLevel(StrEnum):
    """Declarative isolation preference for a Workload."""

    NONE = "none"
    THREAD = "thread"
    PROCESS = "process"
    SUBPROCESS = "subprocess"
    CONTAINER = "container"
    REMOTE = "remote"


class Priority(IntEnum):
    """Declarative Workload priority; it does not guarantee scheduling order."""

    LOW = 10
    NORMAL = 20
    HIGH = 30
    CRITICAL = 40


_TERMINAL_RUN_STATES = frozenset(
    {
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.TIMED_OUT,
        RunState.ABORTED,
    }
)


__all__ = ["IsolationLevel", "Priority", "RunState"]
