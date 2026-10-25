"""Tests for backend-neutral result contracts."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from pyruntimekit.domain import (
    ArtifactId,
    ArtifactRef,
    ExecutionResult,
    Failure,
    FailureCategory,
    FailureCode,
    FailureOrigin,
    FailureScope,
    FailureSeverity,
    RunResult,
)

COMPLETED_AT = datetime(2026, 10, 25, 17, 0, tzinfo=UTC)


def make_failure() -> Failure:
    return Failure.create(
        code=FailureCode("WORKLOAD_EXCEPTION"),
        category=FailureCategory.WORKLOAD,
        origin=FailureOrigin.WORKLOAD,
        severity=FailureSeverity.ERROR,
        scope=FailureScope.ATTEMPT,
        message="workload failed",
        retryable=False,
        recoverable=False,
        occurred_at=COMPLETED_AT,
    )


def make_artifact() -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactId("550e8400-e29b-41d4-a716-446655440000"),
        uri="artifact://results/report.json",
        media_type="application/json",
        checksum="sha256:abc123",
        size=42,
    )


def test_artifact_ref_is_immutable_and_serialization_friendly() -> None:
    artifact = make_artifact()

    assert artifact.to_dict() == {
        "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
        "uri": "artifact://results/report.json",
        "media_type": "application/json",
        "checksum": "sha256:abc123",
        "size": 42,
    }

    with pytest.raises(FrozenInstanceError):
        artifact.__setattr__("size", 99)


def test_artifact_ref_accepts_zero_size() -> None:
    artifact = ArtifactRef(
        artifact_id=ArtifactId.new(),
        uri="artifact://results/empty.txt",
        size=0,
    )

    assert artifact.size == 0


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("uri", {"uri": " "}),
        ("media_type", {"uri": "artifact://x", "media_type": " "}),
        ("checksum", {"uri": "artifact://x", "checksum": ""}),
    ],
)
def test_artifact_ref_rejects_blank_text_fields(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match=field_name):
        ArtifactRef(
            artifact_id=ArtifactId.new(),
            **cast(Any, kwargs),
        )


def test_artifact_ref_rejects_negative_size() -> None:
    with pytest.raises(ValueError, match="greater than or equal to zero"):
        ArtifactRef(
            artifact_id=ArtifactId.new(),
            uri="artifact://x",
            size=-1,
        )


def test_artifact_ref_rejects_non_integer_size() -> None:
    with pytest.raises(TypeError, match="integer"):
        ArtifactRef(
            artifact_id=ArtifactId.new(),
            uri="artifact://x",
            size=cast(Any, True),
        )


def test_artifact_ref_rejects_wrong_identifier_type() -> None:
    with pytest.raises(TypeError, match="ArtifactId"):
        ArtifactRef(
            artifact_id=cast(Any, "artifact-1"),
            uri="artifact://x",
        )


def test_execution_result_success_with_value() -> None:
    result = ExecutionResult[int].success(
        42,
        exit_code=0,
        stdout="done",
        artifacts=(make_artifact(),),
        metadata={"executor": "inline"},
    )

    assert result.succeeded
    assert not result.failed
    assert result.value == 42
    assert result.failure is None
    assert result.exit_code == 0
    assert result.stdout == "done"
    assert result.artifacts == (make_artifact(),)
    assert result.metadata_dict() == {"executor": "inline"}


def test_execution_result_success_with_none_value_is_valid() -> None:
    result = ExecutionResult[None].success()

    assert result.succeeded
    assert result.value is None
    assert result.failure is None


def test_execution_result_failure_contains_no_success_value() -> None:
    failure = make_failure()
    result = ExecutionResult[object].from_failure(
        failure,
        exit_code=1,
        stderr="failed",
        artifacts=(make_artifact(),),
        metadata={"executor": "process"},
    )

    assert result.failed
    assert not result.succeeded
    assert result.value is None
    assert result.failure is failure
    assert result.exit_code == 1
    assert result.stderr == "failed"


def test_execution_result_rejects_value_and_failure_together() -> None:
    with pytest.raises(ValueError, match="cannot also contain a value"):
        ExecutionResult[int](
            value=42,
            failure=make_failure(),
        )


def test_execution_result_rejects_raw_exception_as_failure() -> None:
    with pytest.raises(TypeError, match="Failure"):
        ExecutionResult[object](
            failure=cast(Any, ValueError("boom")),
        )


@pytest.mark.parametrize("value", [True, 1.5, "1"])
def test_execution_result_rejects_non_integer_exit_code(value: object) -> None:
    with pytest.raises(TypeError, match="exit_code"):
        ExecutionResult[object](exit_code=cast(Any, value))


@pytest.mark.parametrize("field_name", ["stdout", "stderr"])
def test_execution_result_rejects_non_string_diagnostic(field_name: str) -> None:
    with pytest.raises(TypeError, match=field_name):
        ExecutionResult[object](**{field_name: cast(Any, 42)})


def test_execution_result_rejects_non_tuple_artifacts() -> None:
    with pytest.raises(TypeError, match="tuple"):
        ExecutionResult[object](artifacts=cast(Any, [make_artifact()]))


def test_execution_result_rejects_non_artifact_ref_item() -> None:
    with pytest.raises(TypeError, match="ArtifactRef"):
        ExecutionResult[object](artifacts=(cast(Any, "artifact"),))


def test_execution_result_metadata_is_defensively_immutable() -> None:
    source: dict[str, object] = {"labels": ["a"]}
    result = ExecutionResult[None].success(metadata=source)

    cast(list[str], source["labels"]).append("mutated")
    detached = result.metadata_dict()
    cast(list[str], detached["labels"]).append("detached")

    assert result.metadata_dict() == {"labels": ["a"]}


def test_execution_result_metadata_rejects_runtime_objects() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        ExecutionResult[None].success(metadata={"runtime": object()})


def test_run_result_success_normalizes_completed_at_to_utc() -> None:
    completed = datetime.fromisoformat("2026-10-25T19:00:00+02:00")
    result = RunResult[str].success(
        completed_at=completed,
        value="done",
        artifacts=(make_artifact(),),
        metadata={"source": "runner"},
    )

    assert result.succeeded
    assert result.value == "done"
    assert result.completed_at == COMPLETED_AT
    assert result.artifacts == (make_artifact(),)
    assert result.metadata_dict() == {"source": "runner"}


def test_run_result_success_with_none_value_is_valid() -> None:
    result = RunResult[None].success(completed_at=COMPLETED_AT)

    assert result.succeeded
    assert result.value is None


def test_run_result_from_failure() -> None:
    failure = make_failure()
    result = RunResult[object].from_failure(
        failure,
        completed_at=COMPLETED_AT,
        artifacts=(make_artifact(),),
        metadata={"source": "runner"},
    )

    assert result.failed
    assert not result.succeeded
    assert result.value is None
    assert result.failure is failure


def test_run_result_rejects_value_and_failure_together() -> None:
    with pytest.raises(ValueError, match="cannot also contain a value"):
        RunResult[int](
            completed_at=COMPLETED_AT,
            value=42,
            failure=make_failure(),
        )


def test_run_result_rejects_raw_exception_as_failure() -> None:
    with pytest.raises(TypeError, match="Failure"):
        RunResult[object](
            completed_at=COMPLETED_AT,
            failure=cast(Any, RuntimeError("boom")),
        )


def test_run_result_rejects_naive_completed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        RunResult[None].success(
            completed_at=datetime(2026, 10, 25, 17, 0),
        )


def test_run_result_rejects_non_tuple_artifacts() -> None:
    with pytest.raises(TypeError, match="tuple"):
        RunResult[None].success(
            completed_at=COMPLETED_AT,
            artifacts=cast(Any, [make_artifact()]),
        )


def test_run_result_rejects_non_artifact_ref_item() -> None:
    with pytest.raises(TypeError, match="ArtifactRef"):
        RunResult[None].success(
            completed_at=COMPLETED_AT,
            artifacts=(cast(Any, "artifact"),),
        )


def test_run_result_metadata_is_defensively_immutable() -> None:
    source: dict[str, object] = {"labels": ["final"]}
    result = RunResult[None].success(
        completed_at=COMPLETED_AT,
        metadata=source,
    )

    cast(list[str], source["labels"]).append("mutated")
    detached = result.metadata_dict()
    cast(list[str], detached["labels"]).append("detached")

    assert result.metadata_dict() == {"labels": ["final"]}


def test_run_result_metadata_rejects_runtime_objects() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        RunResult[None].success(
            completed_at=COMPLETED_AT,
            metadata={"runtime": object()},
        )
