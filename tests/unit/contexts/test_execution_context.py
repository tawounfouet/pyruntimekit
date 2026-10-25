"""Tests for the initial immutable ExecutionContext contract."""

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import AttemptNumber, RunId, WorkloadId


def _context(
    *,
    attempt: AttemptNumber | None = None,
    correlation_id: str = "customer-import-2026-10",
    trace_id: str | None = "trace-001",
    metadata: dict[str, object] | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=WorkloadId.new(),
        attempt=AttemptNumber.first() if attempt is None else attempt,
        correlation_id=correlation_id,
        trace_id=trace_id,
        metadata={} if metadata is None else metadata,
    )


def test_execution_context_construction() -> None:
    run_id = RunId.new()
    workload_id = WorkloadId.new()
    attempt = AttemptNumber.first()

    context = ExecutionContext(
        run_id=run_id,
        workload_id=workload_id,
        attempt=attempt,
        correlation_id=" correlation-42 ",
        trace_id=" trace-abc ",
        metadata={"tenant_id": "tenant-a", "tags": ["alpha"]},
    )

    assert context.run_id == run_id
    assert context.workload_id == workload_id
    assert context.attempt == attempt
    assert context.correlation_id == "correlation-42"
    assert context.trace_id == "trace-abc"
    assert context.metadata_dict() == {
        "tenant_id": "tenant-a",
        "tags": ["alpha"],
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("run_id", "run", "run_id must be a RunId"),
        ("workload_id", "workload", "workload_id must be a WorkloadId"),
        ("attempt", 1, "attempt must be an AttemptNumber"),
    ],
)
def test_execution_context_requires_typed_identity_fields(
    field: str,
    value: object,
    message: str,
) -> None:
    kwargs: dict[str, object] = {
        "run_id": RunId.new(),
        "workload_id": WorkloadId.new(),
        "attempt": AttemptNumber.first(),
        "correlation_id": "corr",
    }
    kwargs[field] = value

    with pytest.raises(TypeError, match=message):
        ExecutionContext(**cast(Any, kwargs))


def test_correlation_id_is_required_non_empty_text() -> None:
    with pytest.raises(ValueError, match="correlation_id must not be empty"):
        _context(correlation_id="   ")


def test_correlation_id_rejects_non_string() -> None:
    with pytest.raises(TypeError, match="correlation_id must be a string"):
        ExecutionContext(
            run_id=RunId.new(),
            workload_id=WorkloadId.new(),
            attempt=AttemptNumber.first(),
            correlation_id=cast(Any, 42),
        )


def test_trace_id_is_optional_and_normalized_when_present() -> None:
    without_trace = _context(trace_id=None)
    with_trace = _context(trace_id=" trace-123 ")

    assert without_trace.trace_id is None
    assert with_trace.trace_id == "trace-123"


def test_trace_id_rejects_empty_or_non_string_values() -> None:
    with pytest.raises(ValueError, match="trace_id must not be empty"):
        _context(trace_id=" ")

    with pytest.raises(TypeError, match="trace_id must be a string"):
        _context(trace_id=cast(Any, 123))


def test_metadata_is_defensively_isolated() -> None:
    metadata: dict[str, object] = {
        "tenant": "demo",
        "tags": ["alpha"],
        "nested": {"priority": 10},
    }

    context = _context(metadata=metadata)

    cast(list[str], metadata["tags"]).append("mutated")
    cast(dict[str, object], metadata["nested"])["priority"] = 99
    metadata["tenant"] = "changed"

    assert context.metadata_dict() == {
        "nested": {"priority": 10},
        "tags": ["alpha"],
        "tenant": "demo",
    }


def test_metadata_mapping_is_immutable_and_detached() -> None:
    context = _context(metadata={"tags": ["alpha"]})

    with pytest.raises(TypeError):
        cast(Any, context.metadata)["new"] = "value"

    detached = context.metadata_dict()
    cast(list[str], detached["tags"]).append("changed")

    assert context.metadata_dict() == {"tags": ["alpha"]}


def test_metadata_rejects_non_json_compatible_values() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        _context(metadata={"bad": object()})


def test_execution_context_is_frozen() -> None:
    context = _context()

    with pytest.raises(FrozenInstanceError):
        context.__setattr__("trace_id", "other")


def test_identity_is_run_id_plus_attempt_number() -> None:
    run_id = RunId.new()
    workload_id = WorkloadId.new()

    first = ExecutionContext(
        run_id=run_id,
        workload_id=workload_id,
        attempt=AttemptNumber(1),
        correlation_id="corr",
    )
    second = ExecutionContext(
        run_id=run_id,
        workload_id=workload_id,
        attempt=AttemptNumber(2),
        correlation_id="corr",
    )

    assert first.identity == (run_id, AttemptNumber(1))
    assert second.identity == (run_id, AttemptNumber(2))
    assert first.identity != second.identity


def test_context_does_not_use_workload_or_correlation_as_identity() -> None:
    run_id = RunId.new()
    attempt = AttemptNumber.first()

    first = ExecutionContext(
        run_id=run_id,
        workload_id=WorkloadId.new(),
        attempt=attempt,
        correlation_id="corr-a",
    )
    second = ExecutionContext(
        run_id=run_id,
        workload_id=WorkloadId.new(),
        attempt=attempt,
        correlation_id="corr-b",
    )

    assert first.identity == second.identity
