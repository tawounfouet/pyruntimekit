"""Tests for Attempt domain contracts."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from pyruntimekit.domain import Attempt, AttemptNumber, AttemptOutcome, RunId

RUN_ID = RunId("550e8400-e29b-41d4-a716-446655440000")
STARTED_AT = datetime(2026, 10, 25, 16, 0, tzinfo=UTC)
FINISHED_AT = STARTED_AT + timedelta(seconds=30)


def test_attempt_number_starts_at_one_and_increments_monotonically() -> None:
    first = AttemptNumber.first()
    second = first.next()

    assert first == AttemptNumber(1)
    assert second == AttemptNumber(2)
    assert second > first


@pytest.mark.parametrize("value", [0, -1])
def test_attempt_number_rejects_non_positive_value(value: int) -> None:
    with pytest.raises(ValueError, match="greater than or equal to one"):
        AttemptNumber(value)


def test_attempt_number_rejects_non_integer_value() -> None:
    with pytest.raises(TypeError, match="integer"):
        AttemptNumber(cast(Any, True))


def test_attempt_outcomes_use_stable_terminal_strings() -> None:
    assert [outcome.value for outcome in AttemptOutcome] == [
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "TIMED_OUT",
    ]


def test_pending_attempt_has_no_timestamps_or_outcome() -> None:
    attempt = Attempt.pending(RUN_ID, AttemptNumber.first())

    assert attempt.is_pending
    assert not attempt.is_running
    assert not attempt.is_finished
    assert attempt.started_at is None
    assert attempt.finished_at is None
    assert attempt.outcome is None


def test_start_returns_running_attempt_and_preserves_identity() -> None:
    pending = Attempt.pending(RUN_ID, AttemptNumber.first())

    running = pending.start(at=STARTED_AT)

    assert pending.is_pending
    assert running.is_running
    assert running.identity == pending.identity
    assert running.started_at == STARTED_AT
    assert running.finished_at is None
    assert running.outcome is None


def test_finish_returns_terminal_attempt() -> None:
    running = Attempt.pending(RUN_ID, AttemptNumber.first()).start(at=STARTED_AT)

    finished = running.finish(AttemptOutcome.SUCCEEDED, at=FINISHED_AT)

    assert finished.is_finished
    assert not finished.is_running
    assert finished.outcome is AttemptOutcome.SUCCEEDED
    assert finished.finished_at == FINISHED_AT


def test_attempt_cannot_be_started_twice() -> None:
    running = Attempt.pending(RUN_ID, AttemptNumber.first()).start(at=STARTED_AT)

    with pytest.raises(ValueError, match="pending"):
        running.start(at=STARTED_AT)


def test_attempt_cannot_be_finished_before_start() -> None:
    pending = Attempt.pending(RUN_ID, AttemptNumber.first())

    with pytest.raises(ValueError, match="running"):
        pending.finish(AttemptOutcome.FAILED, at=FINISHED_AT)


def test_finished_attempt_cannot_be_finished_again() -> None:
    finished = (
        Attempt.pending(RUN_ID, AttemptNumber.first())
        .start(at=STARTED_AT)
        .finish(AttemptOutcome.FAILED, at=FINISHED_AT)
    )

    with pytest.raises(ValueError, match="running"):
        finished.finish(AttemptOutcome.SUCCEEDED, at=FINISHED_AT)


def test_attempt_rejects_naive_started_at() -> None:
    pending = Attempt.pending(RUN_ID, AttemptNumber.first())

    with pytest.raises(ValueError, match="timezone-aware"):
        pending.start(at=datetime(2026, 10, 25, 16, 0))


def test_attempt_rejects_finished_before_started() -> None:
    with pytest.raises(ValueError, match="finished_at"):
        Attempt(
            run_id=RUN_ID,
            number=AttemptNumber.first(),
            started_at=STARTED_AT,
            finished_at=STARTED_AT - timedelta(seconds=1),
            outcome=AttemptOutcome.FAILED,
        )


def test_attempt_rejects_finished_at_without_outcome() -> None:
    with pytest.raises(ValueError, match="set together"):
        Attempt(
            run_id=RUN_ID,
            number=AttemptNumber.first(),
            started_at=STARTED_AT,
            finished_at=FINISHED_AT,
        )


def test_attempt_rejects_outcome_without_finished_at() -> None:
    with pytest.raises(ValueError, match="set together"):
        Attempt(
            run_id=RUN_ID,
            number=AttemptNumber.first(),
            started_at=STARTED_AT,
            outcome=AttemptOutcome.FAILED,
        )


def test_attempt_rejects_terminal_data_without_start() -> None:
    with pytest.raises(ValueError, match="require started_at"):
        Attempt(
            run_id=RUN_ID,
            number=AttemptNumber.first(),
            finished_at=FINISHED_AT,
            outcome=AttemptOutcome.FAILED,
        )


def test_attempt_rejects_non_outcome_value() -> None:
    with pytest.raises(TypeError, match="AttemptOutcome"):
        Attempt(
            run_id=RUN_ID,
            number=AttemptNumber.first(),
            started_at=STARTED_AT,
            finished_at=FINISHED_AT,
            outcome=cast(Any, "FAILED"),
        )


def test_attempt_identity_is_run_id_plus_attempt_number() -> None:
    first = Attempt.pending(RUN_ID, AttemptNumber(2), metadata={"source": "a"})
    second = Attempt(
        run_id=RUN_ID,
        number=AttemptNumber(2),
        started_at=STARTED_AT,
        metadata={"source": "b"},
    )

    assert first == second
    assert hash(first) == hash(second)
    assert first.identity == (RUN_ID, AttemptNumber(2))


def test_attempt_with_different_number_has_different_identity() -> None:
    first = Attempt.pending(RUN_ID, AttemptNumber(1))
    second = Attempt.pending(RUN_ID, AttemptNumber(2))

    assert first != second


def test_attempt_metadata_is_defensively_immutable() -> None:
    source: dict[str, object] = {"labels": ["retry"]}
    attempt = Attempt.pending(RUN_ID, AttemptNumber.first(), metadata=source)

    cast(list[str], source["labels"]).append("mutated")
    detached = attempt.metadata_dict()
    cast(list[str], detached["labels"]).append("detached")

    assert attempt.metadata_dict() == {"labels": ["retry"]}


def test_attempt_metadata_rejects_runtime_objects() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        Attempt.pending(
            RUN_ID,
            AttemptNumber.first(),
            metadata={"runtime": object()},
        )
