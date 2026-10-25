"""Core runtime domain semantics.

This package must remain independent from execution backends, persistence
providers and higher-level framework integrations.
"""

from .attempt import Attempt, AttemptNumber, AttemptOutcome
from .enums import (
    FailureCategory,
    FailureOrigin,
    FailureScope,
    FailureSeverity,
    IsolationLevel,
    Priority,
    RunState,
)
from .events import (
    DomainEvent,
    RunAborted,
    RunAdmitted,
    RunCancelled,
    RunCreated,
    RunFailed,
    RunQueued,
    RunStarted,
    RunSucceeded,
    RunTimedOut,
)
from .exceptions import DomainInvariantError, InvalidRunTransitionError
from .failure import (
    FAILURE_SCHEMA_VERSION,
    Failure,
    FailureCauseSummary,
    FailureCode,
    FailureDetails,
)
from .ids import ArtifactId, EventId, FailureId, RunId, WorkloadId
from .invariants import (
    allowed_next_states,
    is_transition_allowed,
    validate_finished_at_consistency,
    validate_next_attempt_number,
    validate_retry_identity,
    validate_terminal_evidence,
    validate_transition,
)
from .result import ArtifactRef, ExecutionResult, RunResult
from .run import RUN_SNAPSHOT_SCHEMA_VERSION, Run, RunSnapshot, RunVersion
from .workload import ResourceHints, Workload, WorkloadDescriptor, WorkloadRef

__all__ = [
    "FAILURE_SCHEMA_VERSION",
    "RUN_SNAPSHOT_SCHEMA_VERSION",
    "ArtifactId",
    "ArtifactRef",
    "Attempt",
    "AttemptNumber",
    "AttemptOutcome",
    "DomainEvent",
    "DomainInvariantError",
    "EventId",
    "ExecutionResult",
    "Failure",
    "FailureCategory",
    "FailureCauseSummary",
    "FailureCode",
    "FailureDetails",
    "FailureId",
    "FailureOrigin",
    "FailureScope",
    "FailureSeverity",
    "InvalidRunTransitionError",
    "IsolationLevel",
    "Priority",
    "ResourceHints",
    "Run",
    "RunAborted",
    "RunAdmitted",
    "RunCancelled",
    "RunCreated",
    "RunFailed",
    "RunId",
    "RunQueued",
    "RunResult",
    "RunSnapshot",
    "RunStarted",
    "RunState",
    "RunSucceeded",
    "RunTimedOut",
    "RunVersion",
    "Workload",
    "WorkloadDescriptor",
    "WorkloadId",
    "WorkloadRef",
    "allowed_next_states",
    "is_transition_allowed",
    "validate_finished_at_consistency",
    "validate_next_attempt_number",
    "validate_retry_identity",
    "validate_terminal_evidence",
    "validate_transition",
]
