"""Immutable commands interpreted by RuntimeKernel."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from pyruntimekit.domain.attempt import AttemptNumber
from pyruntimekit.domain.failure import Failure
from pyruntimekit.domain.ids import RunId, WorkloadId
from pyruntimekit.domain.result import RunResult
from pyruntimekit.domain.validation import (
    freeze_json_mapping,
    normalize_aware_datetime,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class _TimestampedCommand:
    """Internal base for commands carrying a logical occurrence time."""

    at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "at",
            normalize_aware_datetime(self.at, field_name="at"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateRun(_TimestampedCommand):
    """Create a new Run in CREATED state."""

    workload_id: WorkloadId
    run_id: RunId | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _TimestampedCommand.__post_init__(self)
        if not isinstance(self.workload_id, WorkloadId):
            raise TypeError("workload_id must be a WorkloadId")
        if self.run_id is not None and not isinstance(self.run_id, RunId):
            raise TypeError("run_id must be a RunId or None")
        object.__setattr__(
            self,
            "metadata",
            freeze_json_mapping(self.metadata, field_name="metadata"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class AdmitRun(_TimestampedCommand):
    """Request CREATED -> ADMITTED."""


@dataclass(frozen=True, slots=True, kw_only=True)
class QueueRun(_TimestampedCommand):
    """Request a canonical transition into QUEUED."""


@dataclass(frozen=True, slots=True, kw_only=True)
class StartRun(_TimestampedCommand):
    """Request QUEUED -> RUNNING with the next AttemptNumber."""

    attempt: AttemptNumber

    def __post_init__(self) -> None:
        _TimestampedCommand.__post_init__(self)
        if not isinstance(self.attempt, AttemptNumber):
            raise TypeError("attempt must be an AttemptNumber")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompleteRun:
    """Request RUNNING -> SUCCEEDED with a successful logical RunResult."""

    result: RunResult[object]

    def __post_init__(self) -> None:
        if not isinstance(self.result, RunResult):
            raise TypeError("result must be a RunResult")
        if self.result.failed:
            raise ValueError("CompleteRun requires a successful RunResult")

    @property
    def at(self) -> datetime:
        """Use the result completion time as the transition occurrence time."""
        return self.result.completed_at


@dataclass(frozen=True, slots=True, kw_only=True)
class FailRun(_TimestampedCommand):
    """Request a canonical transition into FAILED with normalized Failure."""

    failure: Failure

    def __post_init__(self) -> None:
        _TimestampedCommand.__post_init__(self)
        if not isinstance(self.failure, Failure):
            raise TypeError("failure must be a Failure")


@dataclass(frozen=True, slots=True, kw_only=True)
class CancelRun(_TimestampedCommand):
    """Request a canonical transition into CANCELLED."""


@dataclass(frozen=True, slots=True, kw_only=True)
class TimeoutRun(_TimestampedCommand):
    """Request a canonical transition into TIMED_OUT."""


@dataclass(frozen=True, slots=True, kw_only=True)
class AbortRun(_TimestampedCommand):
    """Request a canonical transition into ABORTED."""


type RunCommand = (
    AdmitRun | QueueRun | StartRun | CompleteRun | FailRun | CancelRun | TimeoutRun | AbortRun
)

type KernelCommand = CreateRun | RunCommand


__all__ = [
    "AbortRun",
    "AdmitRun",
    "CancelRun",
    "CompleteRun",
    "CreateRun",
    "FailRun",
    "KernelCommand",
    "QueueRun",
    "RunCommand",
    "StartRun",
    "TimeoutRun",
]
