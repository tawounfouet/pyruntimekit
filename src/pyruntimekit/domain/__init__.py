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
from .failure import (
    FAILURE_SCHEMA_VERSION,
    Failure,
    FailureCauseSummary,
    FailureCode,
    FailureDetails,
)
from .ids import EventId, FailureId, RunId, WorkloadId
from .run import RUN_SNAPSHOT_SCHEMA_VERSION, Run, RunSnapshot, RunVersion
from .workload import ResourceHints, Workload, WorkloadDescriptor, WorkloadRef

__all__ = [
    "FAILURE_SCHEMA_VERSION",
    "RUN_SNAPSHOT_SCHEMA_VERSION",
    "Attempt",
    "AttemptNumber",
    "AttemptOutcome",
    "EventId",
    "Failure",
    "FailureCategory",
    "FailureCauseSummary",
    "FailureCode",
    "FailureDetails",
    "FailureId",
    "FailureOrigin",
    "FailureScope",
    "FailureSeverity",
    "IsolationLevel",
    "Priority",
    "ResourceHints",
    "Run",
    "RunId",
    "RunSnapshot",
    "RunState",
    "RunVersion",
    "Workload",
    "WorkloadDescriptor",
    "WorkloadId",
    "WorkloadRef",
]
