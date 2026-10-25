"""Core runtime domain semantics.

This package must remain independent from execution backends, persistence
providers and higher-level framework integrations.
"""

from .enums import RunState
from .ids import EventId, FailureId, RunId, WorkloadId

__all__ = ["EventId", "FailureId", "RunId", "RunState", "WorkloadId"]
