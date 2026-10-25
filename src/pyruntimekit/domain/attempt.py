"""Attempt entity and value objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum

from .ids import RunId
from .validation import freeze_json_mapping, normalize_aware_datetime, plain_json_mapping


@dataclass(frozen=True, order=True, slots=True)
class AttemptNumber:
    """One-based monotone attempt number within a Run."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("attempt number must be an integer")
        if self.value < 1:
            raise ValueError("attempt number must be greater than or equal to one")

    @classmethod
    def first(cls) -> AttemptNumber:
        """Return the first attempt number."""
        return cls(1)

    def next(self) -> AttemptNumber:
        """Return the next monotone attempt number."""
        return type(self)(self.value + 1)


class AttemptOutcome(StrEnum):
    """Terminal outcome of one concrete execution attempt."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


@dataclass(frozen=True, slots=True, eq=False)
class Attempt:
    """Immutable concrete execution attempt belonging to one Run."""

    run_id: RunId
    number: AttemptNumber
    started_at: datetime | None = None
    finished_at: datetime | None = None
    outcome: AttemptOutcome | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        started = (
            None
            if self.started_at is None
            else normalize_aware_datetime(self.started_at, field_name="started_at")
        )
        finished = (
            None
            if self.finished_at is None
            else normalize_aware_datetime(self.finished_at, field_name="finished_at")
        )

        if self.outcome is not None and not isinstance(self.outcome, AttemptOutcome):
            raise TypeError("outcome must be an AttemptOutcome or None")
        if started is None and (finished is not None or self.outcome is not None):
            raise ValueError("finished_at and outcome require started_at")
        if (finished is None) != (self.outcome is None):
            raise ValueError("finished_at and outcome must be set together")
        if started is not None and finished is not None and finished < started:
            raise ValueError("finished_at must not be earlier than started_at")

        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "finished_at", finished)
        object.__setattr__(
            self,
            "metadata",
            freeze_json_mapping(self.metadata, field_name="metadata"),
        )

    @classmethod
    def pending(
        cls,
        run_id: RunId,
        number: AttemptNumber,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> Attempt:
        """Create a pending attempt that has not started yet."""
        return cls(run_id=run_id, number=number, metadata={} if metadata is None else metadata)

    def start(self, *, at: datetime) -> Attempt:
        """Return the RUNNING representation of this pending Attempt."""
        if not self.is_pending:
            raise ValueError("only a pending Attempt can be started")
        return replace(
            self,
            started_at=normalize_aware_datetime(at, field_name="started_at"),
        )

    def finish(self, outcome: AttemptOutcome, *, at: datetime) -> Attempt:
        """Return a terminal representation of this running Attempt."""
        if not self.is_running:
            raise ValueError("only a running Attempt can be finished")
        if not isinstance(outcome, AttemptOutcome):
            raise TypeError("outcome must be an AttemptOutcome")
        return replace(
            self,
            finished_at=normalize_aware_datetime(at, field_name="finished_at"),
            outcome=outcome,
        )

    @property
    def is_pending(self) -> bool:
        return self.started_at is None

    @property
    def is_running(self) -> bool:
        return self.started_at is not None and self.finished_at is None

    @property
    def is_finished(self) -> bool:
        return self.finished_at is not None

    @property
    def identity(self) -> tuple[RunId, AttemptNumber]:
        """Return the logical identity of the Attempt."""
        return (self.run_id, self.number)

    def metadata_dict(self) -> dict[str, object]:
        """Return detached metadata suitable for serialization."""
        return plain_json_mapping(self.metadata)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Attempt):
            return NotImplemented
        return self.identity == other.identity

    def __hash__(self) -> int:
        return hash(self.identity)


__all__ = ["Attempt", "AttemptNumber", "AttemptOutcome"]
