"""Tests for the Run aggregate and Run snapshots."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from pyruntimekit.domain import (
    RUN_SNAPSHOT_SCHEMA_VERSION,
    AttemptNumber,
    Run,
    RunId,
    RunSnapshot,
    RunState,
    RunVersion,
    WorkloadId,
)

RUN_ID = RunId("550e8400-e29b-41d4-a716-446655440000")
WORKLOAD_ID = WorkloadId("123e4567-e89b-12d3-a456-426614174000")
CREATED_AT = datetime(2026, 10, 25, 15, 0, tzinfo=UTC)


def test_run_creation_uses_canonical_initial_state_and_version() -> None:
    run = Run.create(WORKLOAD_ID, run_id=RUN_ID, created_at=CREATED_AT)

    assert run.run_id == RUN_ID
    assert run.workload_id == WORKLOAD_ID
    assert run.state is RunState.CREATED
    assert run.version == RunVersion.initial()
    assert run.current_attempt is None
    assert run.created_at == CREATED_AT
    assert run.updated_at == CREATED_AT
    assert not run.is_terminal


def test_run_create_generates_identifier_when_not_supplied() -> None:
    run = Run.create(WORKLOAD_ID, created_at=CREATED_AT)

    assert isinstance(run.run_id, RunId)


def test_run_creation_rejects_naive_datetime() -> None:
    naive = datetime(2026, 10, 25, 15, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        Run.create(WORKLOAD_ID, created_at=naive)


def test_run_metadata_is_defensively_immutable() -> None:
    source: dict[str, object] = {"labels": ["nightly"]}
    run = Run.create(
        WORKLOAD_ID,
        run_id=RUN_ID,
        created_at=CREATED_AT,
        metadata=source,
    )

    cast(list[str], source["labels"]).append("changed")
    detached = run.metadata_dict()
    cast(list[str], detached["labels"]).append("detached")

    assert run.metadata_dict() == {"labels": ["nightly"]}


def test_run_metadata_rejects_runtime_objects() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        Run.create(
            WORKLOAD_ID,
            created_at=CREATED_AT,
            metadata={"runtime": object()},
        )


def test_run_entity_equality_and_hashing_use_identity_only() -> None:
    first = Run.create(
        WORKLOAD_ID,
        run_id=RUN_ID,
        created_at=CREATED_AT,
        metadata={"a": 1},
    )
    second = Run.create(
        WORKLOAD_ID,
        run_id=RUN_ID,
        created_at=CREATED_AT + timedelta(seconds=5),
        metadata={"b": 2},
    )

    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_run_entity_is_not_equal_to_unrelated_type() -> None:
    run = Run.create(WORKLOAD_ID, run_id=RUN_ID, created_at=CREATED_AT)

    assert run != object()


def test_run_public_state_property_cannot_be_assigned() -> None:
    run = Run.create(WORKLOAD_ID, run_id=RUN_ID, created_at=CREATED_AT)

    with pytest.raises(AttributeError):
        cast(Any, run).state = RunState.SUCCEEDED


def test_run_version_is_non_negative_and_monotone() -> None:
    version = RunVersion.initial()

    assert version.value == 0
    assert version.next() == RunVersion(1)
    assert version.next() > version


def test_run_version_rejects_negative_value() -> None:
    with pytest.raises(ValueError, match="greater than or equal to zero"):
        RunVersion(-1)


def test_run_version_rejects_non_integer_value() -> None:
    with pytest.raises(TypeError, match="integer"):
        RunVersion(cast(Any, True))


def test_run_snapshot_is_stable_serialization_friendly_state() -> None:
    run = Run.create(
        WORKLOAD_ID,
        run_id=RUN_ID,
        created_at=CREATED_AT,
        metadata={"request_id": "req-42"},
    )

    snapshot = run.snapshot()

    assert snapshot.to_dict() == {
        "schema_version": RUN_SNAPSHOT_SCHEMA_VERSION,
        "run_id": RUN_ID.value,
        "workload_id": WORKLOAD_ID.value,
        "state": "CREATED",
        "version": 0,
        "created_at": "2026-10-25T15:00:00Z",
        "updated_at": "2026-10-25T15:00:00Z",
        "current_attempt": None,
        "metadata": {"request_id": "req-42"},
    }


def test_run_snapshot_is_immutable() -> None:
    snapshot = Run.create(
        WORKLOAD_ID,
        run_id=RUN_ID,
        created_at=CREATED_AT,
    ).snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.__setattr__("state", "FAILED")


def test_run_restores_terminal_snapshot_without_running_transition_logic() -> None:
    snapshot = RunSnapshot(
        schema_version=RUN_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID.value,
        workload_id=WORKLOAD_ID.value,
        state="SUCCEEDED",
        version=7,
        created_at="2026-10-25T15:00:00Z",
        updated_at="2026-10-25T15:05:00Z",
        current_attempt=2,
        metadata={"source": "store"},
    )

    run = Run.from_snapshot(snapshot)

    assert run.state is RunState.SUCCEEDED
    assert run.is_terminal
    assert run.version == RunVersion(7)
    assert run.current_attempt == AttemptNumber(2)
    assert run.snapshot().to_dict() == snapshot.to_dict()


def test_run_restoration_rejects_unsupported_snapshot_schema() -> None:
    snapshot = RunSnapshot(
        schema_version=2,
        run_id=RUN_ID.value,
        workload_id=WORKLOAD_ID.value,
        state="CREATED",
        version=0,
        created_at="2026-10-25T15:00:00Z",
        updated_at="2026-10-25T15:00:00Z",
    )

    with pytest.raises(ValueError, match="unsupported"):
        Run.from_snapshot(snapshot)


def test_run_snapshot_rejects_updated_before_created() -> None:
    with pytest.raises(ValueError, match="updated_at"):
        RunSnapshot(
            schema_version=1,
            run_id=RUN_ID.value,
            workload_id=WORKLOAD_ID.value,
            state="CREATED",
            version=0,
            created_at="2026-10-25T15:00:00Z",
            updated_at="2026-10-25T14:59:59Z",
        )


@pytest.mark.parametrize("current_attempt", [0, -1])
def test_run_snapshot_rejects_non_positive_current_attempt(current_attempt: int) -> None:
    with pytest.raises(ValueError, match="current_attempt"):
        RunSnapshot(
            schema_version=1,
            run_id=RUN_ID.value,
            workload_id=WORKLOAD_ID.value,
            state="CREATED",
            version=0,
            created_at="2026-10-25T15:00:00Z",
            updated_at="2026-10-25T15:00:00Z",
            current_attempt=current_attempt,
        )


def test_run_snapshot_rejects_non_integer_current_attempt() -> None:
    with pytest.raises(TypeError, match="current_attempt"):
        RunSnapshot(
            schema_version=1,
            run_id=RUN_ID.value,
            workload_id=WORKLOAD_ID.value,
            state="CREATED",
            version=0,
            created_at="2026-10-25T15:00:00Z",
            updated_at="2026-10-25T15:00:00Z",
            current_attempt=cast(Any, True),
        )


def test_run_snapshot_rejects_invalid_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        RunSnapshot(
            schema_version=0,
            run_id=RUN_ID.value,
            workload_id=WORKLOAD_ID.value,
            state="CREATED",
            version=0,
            created_at="2026-10-25T15:00:00Z",
            updated_at="2026-10-25T15:00:00Z",
        )


def test_run_snapshot_rejects_non_integer_schema_version() -> None:
    with pytest.raises(TypeError, match="schema_version"):
        RunSnapshot(
            schema_version=cast(Any, True),
            run_id=RUN_ID.value,
            workload_id=WORKLOAD_ID.value,
            state="CREATED",
            version=0,
            created_at="2026-10-25T15:00:00Z",
            updated_at="2026-10-25T15:00:00Z",
        )


def test_run_snapshot_rejects_unknown_state() -> None:
    with pytest.raises(ValueError):
        RunSnapshot(
            schema_version=1,
            run_id=RUN_ID.value,
            workload_id=WORKLOAD_ID.value,
            state="UNKNOWN",
            version=0,
            created_at="2026-10-25T15:00:00Z",
            updated_at="2026-10-25T15:00:00Z",
        )


def test_run_snapshot_rejects_naive_datetime_string() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        RunSnapshot(
            schema_version=1,
            run_id=RUN_ID.value,
            workload_id=WORKLOAD_ID.value,
            state="CREATED",
            version=0,
            created_at="2026-10-25T15:00:00",
            updated_at="2026-10-25T15:00:00Z",
        )
