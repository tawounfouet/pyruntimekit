"""Tests for immutable RuntimeKernel command contracts."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

import pytest

from pyruntimekit.domain import (
    AttemptNumber,
    Failure,
    FailureCategory,
    FailureCode,
    FailureOrigin,
    FailureScope,
    FailureSeverity,
    RunId,
    RunResult,
    WorkloadId,
)
from pyruntimekit.kernel import (
    AdmitRun,
    CompleteRun,
    CreateRun,
    FailRun,
    StartRun,
)

NOW = datetime(2026, 10, 25, 21, 0, tzinfo=UTC)


def _failure() -> Failure:
    return Failure.create(
        code=FailureCode("EXECUTION.TEST"),
        category=FailureCategory.EXECUTION,
        origin=FailureOrigin.RUNTIME_KERNEL,
        severity=FailureSeverity.ERROR,
        scope=FailureScope.RUN,
        message="test failure",
        retryable=False,
        recoverable=False,
        occurred_at=NOW,
    )


def test_timestamped_command_normalizes_to_utc() -> None:
    local = datetime(
        2026,
        10,
        25,
        23,
        0,
        tzinfo=timezone(timedelta(hours=2)),
    )

    command = AdmitRun(at=local)

    assert command.at == datetime(2026, 10, 25, 21, 0, tzinfo=UTC)


def test_timestamped_command_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        AdmitRun(at=datetime(2026, 10, 25, 21, 0))


def test_create_run_validates_and_freezes_metadata() -> None:
    nested = {"labels": ["alpha"]}
    command = CreateRun(
        at=NOW,
        workload_id=WorkloadId.new(),
        run_id=RunId.new(),
        metadata=nested,
    )
    nested["labels"].append("mutated")

    assert command.metadata["labels"] == ("alpha",)

    with pytest.raises(TypeError):
        cast(Any, command.metadata)["other"] = "value"


def test_create_run_rejects_invalid_identifier_types() -> None:
    with pytest.raises(TypeError, match="workload_id"):
        CreateRun(at=NOW, workload_id=cast(Any, "workload"))

    with pytest.raises(TypeError, match="run_id"):
        CreateRun(
            at=NOW,
            workload_id=WorkloadId.new(),
            run_id=cast(Any, "run"),
        )


def test_start_run_requires_attempt_number() -> None:
    command = StartRun(at=NOW, attempt=AttemptNumber.first())

    assert command.attempt == AttemptNumber(1)

    with pytest.raises(TypeError, match="AttemptNumber"):
        StartRun(at=NOW, attempt=cast(Any, 1))


def test_complete_run_uses_result_completion_time() -> None:
    result = RunResult[object].success(
        completed_at=NOW,
        value=object(),
    )

    command = CompleteRun(result=result)

    assert command.at == NOW
    assert command.result is result


def test_complete_run_rejects_failed_result() -> None:
    result = RunResult[object].from_failure(
        _failure(),
        completed_at=NOW,
    )

    with pytest.raises(ValueError, match="successful RunResult"):
        CompleteRun(result=result)


def test_complete_run_rejects_non_run_result() -> None:
    with pytest.raises(TypeError, match="RunResult"):
        CompleteRun(result=cast(Any, object()))


def test_fail_run_requires_normalized_failure() -> None:
    failure = _failure()

    command = FailRun(at=NOW, failure=failure)

    assert command.failure is failure

    with pytest.raises(TypeError, match="Failure"):
        FailRun(at=NOW, failure=cast(Any, ValueError("boom")))


def test_commands_are_immutable() -> None:
    command = AdmitRun(at=NOW)

    with pytest.raises(FrozenInstanceError):
        command.__setattr__("at", NOW + timedelta(seconds=1))
