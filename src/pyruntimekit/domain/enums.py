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


class FailureCategory(StrEnum):
    """Normative category describing the nature of a Failure."""

    WORKLOAD = "WORKLOAD"
    VALIDATION = "VALIDATION"
    TRANSIENT_INFRASTRUCTURE = "TRANSIENT_INFRASTRUCTURE"
    PERMANENT_INFRASTRUCTURE = "PERMANENT_INFRASTRUCTURE"
    EXECUTION = "EXECUTION"
    TIMEOUT = "TIMEOUT"
    CANCELLATION = "CANCELLATION"
    WORKER = "WORKER"
    COORDINATION = "COORDINATION"
    PERSISTENCE = "PERSISTENCE"
    SERIALIZATION = "SERIALIZATION"
    CHECKPOINT = "CHECKPOINT"
    RECOVERY = "RECOVERY"
    EFFECT = "EFFECT"
    SECURITY = "SECURITY"
    POLICY = "POLICY"
    INVARIANT = "INVARIANT"
    CONFIGURATION = "CONFIGURATION"
    COMPATIBILITY = "COMPATIBILITY"
    UNKNOWN = "UNKNOWN"


class FailureOrigin(StrEnum):
    """Normative origin identifying where a Failure was observed."""

    WORKLOAD = "WORKLOAD"
    RUNNER = "RUNNER"
    EXECUTOR = "EXECUTOR"
    WORKER = "WORKER"
    RUNTIME_KERNEL = "RUNTIME_KERNEL"
    STORE = "STORE"
    COORDINATION = "COORDINATION"
    CHECKPOINT = "CHECKPOINT"
    EFFECT = "EFFECT"
    POLICY = "POLICY"
    ADAPTER = "ADAPTER"
    REMOTE_SYSTEM = "REMOTE_SYSTEM"
    UNKNOWN = "UNKNOWN"


class FailureSeverity(StrEnum):
    """Normative severity of a Failure."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class FailureScope(StrEnum):
    """Normative scope describing the impact radius of a Failure."""

    ATTEMPT = "ATTEMPT"
    RUN = "RUN"
    WORKER = "WORKER"
    RUNTIME = "RUNTIME"
    SYSTEM = "SYSTEM"


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


__all__ = [
    "FailureCategory",
    "FailureOrigin",
    "FailureScope",
    "FailureSeverity",
    "IsolationLevel",
    "Priority",
    "RunState",
]
