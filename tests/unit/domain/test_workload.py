"""Tests for the backend-agnostic Workload model."""

import json
from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from pyruntimekit.domain import (
    IsolationLevel,
    Priority,
    ResourceHints,
    Workload,
    WorkloadDescriptor,
    WorkloadId,
    WorkloadRef,
)


def test_workload_descriptor_is_serialization_friendly() -> None:
    descriptor = WorkloadDescriptor(
        kind="python.callable",
        reference="example.jobs:generate_report",
        parameters={"month": "2026-10", "pages": [1, 2]},
        schema_version=2,
    )

    assert descriptor.to_dict() == {
        "kind": "python.callable",
        "reference": "example.jobs:generate_report",
        "parameters": {"month": "2026-10", "pages": [1, 2]},
        "schema_version": 2,
    }


def test_descriptor_parameters_are_defensively_immutable() -> None:
    original: dict[str, object] = {"config": {"retries": 2}}
    descriptor = WorkloadDescriptor(kind="custom", reference="jobs:v1", parameters=original)

    cast(dict[str, object], original["config"])["retries"] = 99
    detached = descriptor.to_dict()
    cast(dict[str, object], detached["parameters"])["new"] = True

    assert descriptor.to_dict()["parameters"] == {"config": {"retries": 2}}


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    (
        ("kind", {"kind": " ", "reference": "job"}),
        ("reference", {"kind": "custom", "reference": ""}),
    ),
)
def test_descriptor_rejects_blank_identity_fields(
    field_name: str, kwargs: dict[str, object]
) -> None:
    with pytest.raises(ValueError, match=field_name):
        WorkloadDescriptor(**cast(Any, kwargs))


def test_descriptor_rejects_invalid_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        WorkloadDescriptor(kind="custom", reference="job", schema_version=0)


def test_descriptor_rejects_non_integer_schema_version() -> None:
    invalid = cast(Any, True)
    with pytest.raises(TypeError, match="schema_version"):
        WorkloadDescriptor(kind="custom", reference="job", schema_version=invalid)


def test_descriptor_rejects_runtime_object_in_parameters() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        WorkloadDescriptor(
            kind="custom",
            reference="job",
            parameters={"callable": object()},
        )


def test_descriptor_rejects_non_finite_number() -> None:
    with pytest.raises(ValueError, match="NaN or infinity"):
        WorkloadDescriptor(
            kind="custom",
            reference="job",
            parameters={"score": float("nan")},
        )


def test_descriptor_rejects_non_string_nested_mapping_key() -> None:
    parameters = cast(dict[str, object], {"nested": {1: "invalid"}})
    with pytest.raises(TypeError, match="keys must be strings"):
        WorkloadDescriptor(kind="custom", reference="job", parameters=parameters)


def test_resource_hints_defaults_are_declarative() -> None:
    hints = ResourceHints()

    assert hints == ResourceHints(
        cpu_bound=False,
        io_bound=False,
        memory_mb=None,
        gpu_required=False,
        isolation=IsolationLevel.NONE,
        priority=Priority.NORMAL,
    )


def test_resource_hints_accept_explicit_preferences() -> None:
    hints = ResourceHints(
        cpu_bound=True,
        memory_mb=2048,
        gpu_required=True,
        isolation=IsolationLevel.PROCESS,
        priority=Priority.HIGH,
    )

    assert hints.memory_mb == 2048
    assert hints.isolation is IsolationLevel.PROCESS
    assert hints.priority is Priority.HIGH


def test_resource_hints_reject_non_positive_memory() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        ResourceHints(memory_mb=0)


def test_resource_hints_reject_non_integer_memory() -> None:
    invalid = cast(Any, True)
    with pytest.raises(TypeError, match="integer or None"):
        ResourceHints(memory_mb=invalid)


def test_workload_exposes_definition_without_execution_backend() -> None:
    descriptor = WorkloadDescriptor(
        kind="agent.run",
        reference="research.manager",
        parameters={"topic": "runtime safety"},
    )
    workload = Workload(
        workload_id=WorkloadId.new(),
        descriptor=descriptor,
        metadata={"source": "test"},
        resource_hints=ResourceHints(io_bound=True),
        policy_refs=("retry.default",),
    )

    assert workload.kind == "agent.run"
    assert workload.parameters["topic"] == "runtime safety"
    assert workload.metadata_dict() == {"source": "test"}
    assert workload.policy_refs == ("retry.default",)
    assert workload.ref.descriptor is descriptor


def test_workload_identity_is_immutable() -> None:
    workload = Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(kind="custom", reference="job"),
    )

    with pytest.raises(FrozenInstanceError):
        workload.__setattr__("workload_id", WorkloadId.new())


def test_workload_metadata_is_defensively_immutable() -> None:
    original: dict[str, object] = {"labels": ["a", "b"]}
    workload = Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(kind="custom", reference="job"),
        metadata=original,
    )

    cast(list[str], original["labels"]).append("c")
    detached = workload.metadata_dict()
    cast(list[str], detached["labels"]).append("d")

    assert workload.metadata_dict() == {"labels": ["a", "b"]}


def test_workload_rejects_invalid_metadata() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        Workload(
            workload_id=WorkloadId.new(),
            descriptor=WorkloadDescriptor(kind="custom", reference="job"),
            metadata={"runtime": object()},
        )


def test_workload_rejects_blank_policy_reference() -> None:
    with pytest.raises(ValueError, match="policy_ref"):
        Workload(
            workload_id=WorkloadId.new(),
            descriptor=WorkloadDescriptor(kind="custom", reference="job"),
            policy_refs=("retry.default", " "),
        )


def test_workload_ref_has_stable_canonical_representation() -> None:
    workload_id = WorkloadId("550e8400-e29b-41d4-a716-446655440000")
    first = WorkloadRef(
        workload_id,
        WorkloadDescriptor(
            kind="custom",
            reference="jobs:v1",
            parameters={"b": 2, "a": 1},
        ),
    )
    second = WorkloadRef(
        workload_id,
        WorkloadDescriptor(
            kind="custom",
            reference="jobs:v1",
            parameters={"a": 1, "b": 2},
        ),
    )

    assert first.to_string() == second.to_string()
    assert str(first) == first.to_string()


def test_workload_ref_round_trips() -> None:
    reference = WorkloadRef(
        WorkloadId("550e8400-e29b-41d4-a716-446655440000"),
        WorkloadDescriptor(
            kind="python.callable",
            reference="example.jobs:run",
            parameters={"args": [1, 2], "enabled": True},
            schema_version=3,
        ),
    )

    restored = WorkloadRef.from_string(reference.to_string())

    assert restored.workload_id == reference.workload_id
    assert restored.descriptor.to_dict() == reference.descriptor.to_dict()
    assert restored.to_string() == reference.to_string()


@pytest.mark.parametrize(
    "value",
    (
        "not-json",
        "[]",
        '{"descriptor": {}}',
        '{"workload_id": "550e8400-e29b-41d4-a716-446655440000", "descriptor": []}',
    ),
)
def test_workload_ref_rejects_malformed_representation(value: str) -> None:
    with pytest.raises(ValueError):
        WorkloadRef.from_string(value)


def test_workload_ref_rejects_non_string_input() -> None:
    with pytest.raises(TypeError):
        WorkloadRef.from_string(cast(Any, 123))


def test_workload_ref_rejects_invalid_descriptor_fields() -> None:
    payload = {
        "workload_id": "550e8400-e29b-41d4-a716-446655440000",
        "descriptor": {
            "kind": 42,
            "reference": "job",
            "parameters": {},
            "schema_version": 1,
        },
    }
    with pytest.raises(ValueError, match="kind and reference"):
        WorkloadRef.from_string(json.dumps(payload))


def test_workload_ref_rejects_invalid_parameters_shape() -> None:
    payload = {
        "workload_id": "550e8400-e29b-41d4-a716-446655440000",
        "descriptor": {
            "kind": "custom",
            "reference": "job",
            "parameters": [],
            "schema_version": 1,
        },
    }
    with pytest.raises(ValueError, match="parameters"):
        WorkloadRef.from_string(json.dumps(payload))


def test_workload_ref_rejects_invalid_schema_version_shape() -> None:
    payload = {
        "workload_id": "550e8400-e29b-41d4-a716-446655440000",
        "descriptor": {
            "kind": "custom",
            "reference": "job",
            "parameters": {},
            "schema_version": True,
        },
    }
    with pytest.raises(ValueError, match="schema_version"):
        WorkloadRef.from_string(json.dumps(payload))


def test_isolation_and_priority_values_are_stable() -> None:
    assert [level.value for level in IsolationLevel] == [
        "none",
        "thread",
        "process",
        "subprocess",
        "container",
        "remote",
    ]
    assert [priority.value for priority in Priority] == [10, 20, 30, 40]
