"""Tests for the normalized Failure domain model."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from pyruntimekit.domain import (
    FAILURE_SCHEMA_VERSION,
    Failure,
    FailureCategory,
    FailureCauseSummary,
    FailureCode,
    FailureDetails,
    FailureId,
    FailureOrigin,
    FailureScope,
    FailureSeverity,
)

FAILURE_ID = FailureId("550e8400-e29b-41d4-a716-446655440000")
OCCURRED_AT = datetime(2026, 10, 25, 16, 30, tzinfo=UTC)


def make_failure() -> Failure:
    return Failure(
        failure_id=FAILURE_ID,
        code=FailureCode("WORKLOAD_EXCEPTION"),
        category=FailureCategory.WORKLOAD,
        origin=FailureOrigin.WORKLOAD,
        severity=FailureSeverity.ERROR,
        scope=FailureScope.ATTEMPT,
        message="workload raised an exception",
        retryable=False,
        recoverable=False,
        occurred_at=OCCURRED_AT,
        details=FailureDetails({"operation": "run"}),
        cause=FailureCauseSummary("ValueError", "invalid value"),
        traceback_ref="artifact://tracebacks/failure-1",
        metadata={"source": "test"},
    )


def test_failure_category_taxonomy_matches_normative_spec() -> None:
    assert [item.value for item in FailureCategory] == [
        "WORKLOAD",
        "VALIDATION",
        "TRANSIENT_INFRASTRUCTURE",
        "PERMANENT_INFRASTRUCTURE",
        "EXECUTION",
        "TIMEOUT",
        "CANCELLATION",
        "WORKER",
        "COORDINATION",
        "PERSISTENCE",
        "SERIALIZATION",
        "CHECKPOINT",
        "RECOVERY",
        "EFFECT",
        "SECURITY",
        "POLICY",
        "INVARIANT",
        "CONFIGURATION",
        "COMPATIBILITY",
        "UNKNOWN",
    ]


def test_failure_origin_taxonomy_matches_normative_spec() -> None:
    assert [item.value for item in FailureOrigin] == [
        "WORKLOAD",
        "RUNNER",
        "EXECUTOR",
        "WORKER",
        "RUNTIME_KERNEL",
        "STORE",
        "COORDINATION",
        "CHECKPOINT",
        "EFFECT",
        "POLICY",
        "ADAPTER",
        "REMOTE_SYSTEM",
        "UNKNOWN",
    ]


def test_failure_severity_taxonomy_matches_normative_spec() -> None:
    assert [item.value for item in FailureSeverity] == [
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
        "FATAL",
    ]


def test_failure_scope_taxonomy_matches_normative_spec() -> None:
    assert [item.value for item in FailureScope] == [
        "ATTEMPT",
        "RUN",
        "WORKER",
        "RUNTIME",
        "SYSTEM",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "WORKLOAD_EXCEPTION",
        "STORE.CONFLICT",
        "PRK-WORKLOAD-001",
        "CHECKPOINT_CORRUPTED",
    ],
)
def test_failure_code_accepts_stable_symbolic_values(value: str) -> None:
    code = FailureCode(value)

    assert code.value == value
    assert str(code) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "workload_exception",
        "WORKLOAD EXCEPTION",
        "_WORKLOAD",
        "WORKLOAD_",
        "WORKLOAD__EXCEPTION",
    ],
)
def test_failure_code_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        FailureCode(value)


def test_failure_code_rejects_non_string_value() -> None:
    with pytest.raises(TypeError):
        FailureCode(cast(Any, 123))


def test_failure_details_are_defensively_immutable() -> None:
    source: dict[str, object] = {"http": {"status": 503}}
    details = FailureDetails(source)

    cast(dict[str, object], source["http"])["status"] = 200
    detached = details.to_dict()
    cast(dict[str, object], detached["http"])["status"] = 201

    assert details.to_dict() == {"http": {"status": 503}}


def test_failure_details_reject_runtime_objects() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        FailureDetails({"exception": object()})


def test_failure_cause_summary_is_serializable() -> None:
    cause = FailureCauseSummary("ValueError", "invalid value")

    assert cause.to_dict() == {
        "type_name": "ValueError",
        "message": "invalid value",
    }


def test_failure_cause_summary_allows_missing_message() -> None:
    cause = FailureCauseSummary("WorkerLost")

    assert cause.to_dict() == {
        "type_name": "WorkerLost",
        "message": None,
    }


def test_failure_cause_summary_rejects_blank_type() -> None:
    with pytest.raises(ValueError, match="type_name"):
        FailureCauseSummary(" ")


def test_failure_cause_summary_rejects_blank_message() -> None:
    with pytest.raises(ValueError, match="cause message"):
        FailureCauseSummary("ValueError", " ")


def test_failure_is_immutable_and_normalized() -> None:
    failure = make_failure()

    assert failure.failure_id == FAILURE_ID
    assert failure.code == FailureCode("WORKLOAD_EXCEPTION")
    assert failure.category is FailureCategory.WORKLOAD
    assert failure.origin is FailureOrigin.WORKLOAD
    assert failure.severity is FailureSeverity.ERROR
    assert failure.scope is FailureScope.ATTEMPT
    assert failure.occurred_at == OCCURRED_AT
    assert failure.schema_version == FAILURE_SCHEMA_VERSION

    with pytest.raises(FrozenInstanceError):
        failure.__setattr__("retryable", True)


def test_failure_normalizes_aware_timestamp_to_utc() -> None:
    offset = datetime.fromisoformat("2026-10-25T18:30:00+02:00")
    failure = replace(make_failure(), occurred_at=offset)

    assert failure.occurred_at == OCCURRED_AT


def test_failure_serialization_is_stable_and_json_compatible() -> None:
    failure = make_failure()

    payload = failure.to_dict()

    assert payload == {
        "schema_version": FAILURE_SCHEMA_VERSION,
        "failure_id": FAILURE_ID.value,
        "code": "WORKLOAD_EXCEPTION",
        "category": "WORKLOAD",
        "origin": "WORKLOAD",
        "severity": "ERROR",
        "scope": "ATTEMPT",
        "message": "workload raised an exception",
        "retryable": False,
        "recoverable": False,
        "occurred_at": "2026-10-25T16:30:00Z",
        "details": {"operation": "run"},
        "cause": {"type_name": "ValueError", "message": "invalid value"},
        "traceback_ref": "artifact://tracebacks/failure-1",
        "metadata": {"source": "test"},
    }
    assert json.loads(json.dumps(payload)) == payload


def test_failure_serialization_allows_missing_optional_fields() -> None:
    failure = replace(
        make_failure(),
        cause=None,
        traceback_ref=None,
        details=FailureDetails(),
        metadata={},
    )

    assert failure.to_dict()["cause"] is None
    assert failure.to_dict()["traceback_ref"] is None
    assert failure.to_dict()["details"] == {}
    assert failure.to_dict()["metadata"] == {}


def test_failure_create_generates_identity_and_timestamp() -> None:
    before = datetime.now(UTC)
    failure = Failure.create(
        code=FailureCode("STORE_UNAVAILABLE"),
        category=FailureCategory.TRANSIENT_INFRASTRUCTURE,
        origin=FailureOrigin.STORE,
        severity=FailureSeverity.ERROR,
        scope=FailureScope.RUN,
        message="store unavailable",
        retryable=True,
        recoverable=False,
    )
    after = datetime.now(UTC)

    assert isinstance(failure.failure_id, FailureId)
    assert before <= failure.occurred_at <= after
    assert failure.details == FailureDetails()
    assert failure.metadata == {}


def test_failure_create_accepts_explicit_identity_time_and_payloads() -> None:
    failure = Failure.create(
        code=FailureCode("WORKER_LOST"),
        category=FailureCategory.WORKER,
        origin=FailureOrigin.WORKER,
        severity=FailureSeverity.ERROR,
        scope=FailureScope.RUN,
        message="worker disappeared",
        retryable=False,
        recoverable=True,
        details=FailureDetails({"worker": "worker-1"}),
        cause=FailureCauseSummary("HeartbeatExpired"),
        traceback_ref="artifact://tracebacks/worker-lost",
        metadata={"region": "eu-west"},
        failure_id=FAILURE_ID,
        occurred_at=OCCURRED_AT,
    )

    assert failure.failure_id == FAILURE_ID
    assert failure.occurred_at == OCCURRED_AT
    assert failure.recoverable
    assert not failure.retryable


def test_failure_metadata_is_defensively_immutable() -> None:
    source: dict[str, object] = {"labels": ["runtime"]}
    failure = replace(make_failure(), metadata=source)

    cast(list[str], source["labels"]).append("mutated")
    detached = failure.to_dict()["metadata"]
    cast(list[str], cast(dict[str, object], detached)["labels"]).append("detached")

    assert failure.to_dict()["metadata"] == {"labels": ["runtime"]}


def test_failure_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(make_failure(), occurred_at=datetime(2026, 10, 25, 16, 30))


def test_failure_rejects_blank_message() -> None:
    with pytest.raises(ValueError, match="message"):
        replace(make_failure(), message=" ")


def test_failure_rejects_blank_traceback_ref() -> None:
    with pytest.raises(ValueError, match="traceback_ref"):
        replace(make_failure(), traceback_ref=" ")


def test_failure_rejects_invalid_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        replace(make_failure(), schema_version=0)


def test_failure_rejects_non_integer_schema_version() -> None:
    with pytest.raises(TypeError, match="schema_version"):
        replace(make_failure(), schema_version=cast(Any, True))


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("failure_id", "id", "FailureId"),
        ("code", "WORKLOAD_EXCEPTION", "FailureCode"),
        ("category", "WORKLOAD", "FailureCategory"),
        ("origin", "WORKLOAD", "FailureOrigin"),
        ("severity", "ERROR", "FailureSeverity"),
        ("scope", "ATTEMPT", "FailureScope"),
        ("retryable", 1, "bool"),
        ("recoverable", 0, "bool"),
        ("details", {}, "FailureDetails"),
        ("cause", ValueError("boom"), "FailureCauseSummary"),
    ],
)
def test_failure_rejects_invalid_contract_types(
    field_name: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        replace(make_failure(), **{field_name: cast(Any, value)})


def test_failure_metadata_rejects_runtime_objects() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        replace(make_failure(), metadata={"exception": object()})


def test_failure_string_and_repr_do_not_expose_diagnostic_payloads() -> None:
    failure = make_failure()

    text = str(failure)
    representation = repr(failure)

    assert text == "WORKLOAD_EXCEPTION [WORKLOAD/WORKLOAD]"
    assert "workload raised an exception" not in text
    assert "invalid value" not in text
    assert "operation" not in text
    assert "workload raised an exception" not in representation
    assert "invalid value" not in representation
    assert "operation" not in representation
    assert "artifact://tracebacks/failure-1" not in representation
    assert "source" not in representation
