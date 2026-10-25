"""Immutable domain events for the Run aggregate."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar, Self

from .ids import EventId, RunId
from .run import RunVersion
from .validation import (
    datetime_to_utc_iso,
    freeze_json_mapping,
    normalize_aware_datetime,
    plain_json_mapping,
    require_text,
)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Immutable fact emitted by the Run domain."""

    EVENT_TYPE: ClassVar[str] = ""
    EVENT_VERSION: ClassVar[int] = 1

    event_id: EventId
    run_id: RunId
    aggregate_version: RunVersion
    occurred_at: datetime
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self) is DomainEvent:
            raise TypeError("DomainEvent must be specialized")
        if not isinstance(self.event_id, EventId):
            raise TypeError("event_id must be an EventId")
        if not isinstance(self.run_id, RunId):
            raise TypeError("run_id must be a RunId")
        if not isinstance(self.aggregate_version, RunVersion):
            raise TypeError("aggregate_version must be a RunVersion")

        require_text(type(self).EVENT_TYPE, field_name="event_type")
        if (
            isinstance(type(self).EVENT_VERSION, bool)
            or not isinstance(type(self).EVENT_VERSION, int)
            or type(self).EVENT_VERSION < 1
        ):
            raise ValueError("event_version must be a positive integer")

        object.__setattr__(
            self,
            "occurred_at",
            normalize_aware_datetime(self.occurred_at, field_name="occurred_at"),
        )
        object.__setattr__(
            self,
            "payload",
            freeze_json_mapping(self.payload, field_name="event payload"),
        )

    @classmethod
    def create(
        cls,
        *,
        run_id: RunId,
        aggregate_version: RunVersion,
        occurred_at: datetime | None = None,
        payload: Mapping[str, object] | None = None,
        event_id: EventId | None = None,
    ) -> Self:
        """Create a domain event with generated identity/time when omitted."""
        return cls(
            event_id=EventId.new() if event_id is None else event_id,
            run_id=run_id,
            aggregate_version=aggregate_version,
            occurred_at=datetime.now(UTC) if occurred_at is None else occurred_at,
            payload={} if payload is None else payload,
        )

    @property
    def event_type(self) -> str:
        """Return the canonical stable event type."""
        return type(self).EVENT_TYPE

    @property
    def event_version(self) -> int:
        """Return the version of this event contract."""
        return type(self).EVENT_VERSION

    def payload_dict(self) -> dict[str, object]:
        """Return detached event payload suitable for serialization."""
        return plain_json_mapping(self.payload)

    def to_dict(self) -> dict[str, object]:
        """Return the stable serialization-friendly event representation."""
        return {
            "event_id": self.event_id.value,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "occurred_at": datetime_to_utc_iso(self.occurred_at, field_name="occurred_at"),
            "run_id": self.run_id.value,
            "aggregate_version": self.aggregate_version.value,
            "payload": self.payload_dict(),
        }


@dataclass(frozen=True, slots=True)
class RunCreated(DomainEvent):
    """Fact that a Run was created."""

    EVENT_TYPE: ClassVar[str] = "run.created"


@dataclass(frozen=True, slots=True)
class RunAdmitted(DomainEvent):
    """Fact that a Run was admitted."""

    EVENT_TYPE: ClassVar[str] = "run.admitted"


@dataclass(frozen=True, slots=True)
class RunQueued(DomainEvent):
    """Fact that a Run was queued."""

    EVENT_TYPE: ClassVar[str] = "run.queued"


@dataclass(frozen=True, slots=True)
class RunStarted(DomainEvent):
    """Fact that a Run started."""

    EVENT_TYPE: ClassVar[str] = "run.started"


@dataclass(frozen=True, slots=True)
class RunSucceeded(DomainEvent):
    """Fact that a Run succeeded."""

    EVENT_TYPE: ClassVar[str] = "run.succeeded"


@dataclass(frozen=True, slots=True)
class RunFailed(DomainEvent):
    """Fact that a Run failed."""

    EVENT_TYPE: ClassVar[str] = "run.failed"


@dataclass(frozen=True, slots=True)
class RunCancelled(DomainEvent):
    """Fact that a Run was cancelled."""

    EVENT_TYPE: ClassVar[str] = "run.cancelled"


@dataclass(frozen=True, slots=True)
class RunTimedOut(DomainEvent):
    """Fact that a Run timed out."""

    EVENT_TYPE: ClassVar[str] = "run.timed_out"


@dataclass(frozen=True, slots=True)
class RunAborted(DomainEvent):
    """Fact that a Run was aborted."""

    EVENT_TYPE: ClassVar[str] = "run.aborted"


__all__ = [
    "DomainEvent",
    "RunAborted",
    "RunAdmitted",
    "RunCancelled",
    "RunCreated",
    "RunFailed",
    "RunQueued",
    "RunStarted",
    "RunSucceeded",
    "RunTimedOut",
]
