"""Tests for immutable Run domain events."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from pyruntimekit.domain import (
    DomainEvent,
    EventId,
    RunAborted,
    RunAdmitted,
    RunCancelled,
    RunCreated,
    RunFailed,
    RunId,
    RunQueued,
    RunStarted,
    RunSucceeded,
    RunTimedOut,
    RunVersion,
)

EVENT_ID = EventId("550e8400-e29b-41d4-a716-446655440000")
RUN_ID = RunId("123e4567-e89b-12d3-a456-426614174000")
OCCURRED_AT = datetime(2026, 10, 25, 17, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("event_class", "event_type"),
    [
        (RunCreated, "run.created"),
        (RunAdmitted, "run.admitted"),
        (RunQueued, "run.queued"),
        (RunStarted, "run.started"),
        (RunSucceeded, "run.succeeded"),
        (RunFailed, "run.failed"),
        (RunCancelled, "run.cancelled"),
        (RunTimedOut, "run.timed_out"),
        (RunAborted, "run.aborted"),
    ],
)
def test_initial_event_types_are_stable(
    event_class: type[DomainEvent],
    event_type: str,
) -> None:
    event = event_class(
        event_id=EVENT_ID,
        run_id=RUN_ID,
        aggregate_version=RunVersion(3),
        occurred_at=OCCURRED_AT,
    )

    assert event.event_type == event_type
    assert event.event_version == 1


def test_domain_event_base_must_be_specialized() -> None:
    with pytest.raises(TypeError, match="specialized"):
        DomainEvent(
            event_id=EVENT_ID,
            run_id=RUN_ID,
            aggregate_version=RunVersion(1),
            occurred_at=OCCURRED_AT,
        )


def test_event_create_generates_identity_and_timestamp() -> None:
    before = datetime.now(UTC)
    event = RunCreated.create(
        run_id=RUN_ID,
        aggregate_version=RunVersion.initial(),
    )
    after = datetime.now(UTC)

    assert isinstance(event.event_id, EventId)
    assert before <= event.occurred_at <= after
    assert event.run_id == RUN_ID
    assert event.aggregate_version == RunVersion(0)


def test_event_create_accepts_explicit_identity_time_and_payload() -> None:
    event = RunStarted.create(
        event_id=EVENT_ID,
        run_id=RUN_ID,
        aggregate_version=RunVersion(4),
        occurred_at=OCCURRED_AT,
        payload={"attempt": 2},
    )

    assert event.event_id == EVENT_ID
    assert event.occurred_at == OCCURRED_AT
    assert event.payload_dict() == {"attempt": 2}


def test_event_normalizes_aware_timestamp_to_utc() -> None:
    offset = datetime.fromisoformat("2026-10-25T19:30:00+02:00")
    event = RunStarted.create(
        event_id=EVENT_ID,
        run_id=RUN_ID,
        aggregate_version=RunVersion(4),
        occurred_at=offset,
    )

    assert event.occurred_at == OCCURRED_AT


def test_event_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        RunStarted.create(
            run_id=RUN_ID,
            aggregate_version=RunVersion(4),
            occurred_at=datetime(2026, 10, 25, 17, 30),
        )


def test_event_payload_is_defensively_immutable() -> None:
    source: dict[str, object] = {"details": {"attempt": 2}}
    event = RunFailed.create(
        event_id=EVENT_ID,
        run_id=RUN_ID,
        aggregate_version=RunVersion(5),
        occurred_at=OCCURRED_AT,
        payload=source,
    )

    cast(dict[str, object], source["details"])["attempt"] = 99
    detached = event.payload_dict()
    cast(dict[str, object], detached["details"])["attempt"] = 100

    assert event.payload_dict() == {"details": {"attempt": 2}}


def test_event_payload_rejects_runtime_objects() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        RunFailed.create(
            run_id=RUN_ID,
            aggregate_version=RunVersion(5),
            occurred_at=OCCURRED_AT,
            payload={"runtime": object()},
        )


def test_event_is_immutable() -> None:
    event = RunSucceeded.create(
        event_id=EVENT_ID,
        run_id=RUN_ID,
        aggregate_version=RunVersion(6),
        occurred_at=OCCURRED_AT,
    )

    with pytest.raises(FrozenInstanceError):
        event.__setattr__("payload", {"changed": True})


def test_event_serialization_is_stable() -> None:
    event = RunSucceeded.create(
        event_id=EVENT_ID,
        run_id=RUN_ID,
        aggregate_version=RunVersion(6),
        occurred_at=OCCURRED_AT,
        payload={"artifact_count": 2},
    )

    assert event.to_dict() == {
        "event_id": EVENT_ID.value,
        "event_type": "run.succeeded",
        "event_version": 1,
        "occurred_at": "2026-10-25T17:30:00Z",
        "run_id": RUN_ID.value,
        "aggregate_version": 6,
        "payload": {"artifact_count": 2},
    }


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("event_id", "event", "EventId"),
        ("run_id", "run", "RunId"),
        ("aggregate_version", 1, "RunVersion"),
    ],
)
def test_event_rejects_invalid_contract_types(
    field_name: str,
    value: object,
    message: str,
) -> None:
    kwargs: dict[str, object] = {
        "event_id": EVENT_ID,
        "run_id": RUN_ID,
        "aggregate_version": RunVersion(1),
        "occurred_at": OCCURRED_AT,
    }
    kwargs[field_name] = value

    with pytest.raises(TypeError, match=message):
        RunQueued(**cast(Any, kwargs))


def test_aggregate_version_zero_is_valid_for_created_event() -> None:
    event = RunCreated.create(
        event_id=EVENT_ID,
        run_id=RUN_ID,
        aggregate_version=RunVersion.initial(),
        occurred_at=OCCURRED_AT,
    )

    assert event.aggregate_version.value == 0


def test_different_events_keep_same_run_identity_and_ordering_version() -> None:
    admitted = RunAdmitted.create(
        run_id=RUN_ID,
        aggregate_version=RunVersion(1),
        occurred_at=OCCURRED_AT,
    )
    queued = RunQueued.create(
        run_id=RUN_ID,
        aggregate_version=RunVersion(2),
        occurred_at=OCCURRED_AT,
    )

    assert admitted.run_id == queued.run_id
    assert admitted.aggregate_version < queued.aggregate_version
