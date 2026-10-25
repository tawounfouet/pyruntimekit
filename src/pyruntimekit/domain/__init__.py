"""Core runtime domain semantics.

This package must remain independent from execution backends, persistence
providers and higher-level framework integrations.
"""

from .enums import IsolationLevel, Priority, RunState
from .ids import EventId, FailureId, RunId, WorkloadId
from .run import RUN_SNAPSHOT_SCHEMA_VERSION, Run, RunSnapshot, RunVersion
from .workload import ResourceHints, Workload, WorkloadDescriptor, WorkloadRef

__all__ = [
    "EventId",
    "FailureId",
    "IsolationLevel",
    "Priority",
    "RUN_SNAPSHOT_SCHEMA_VERSION",
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
