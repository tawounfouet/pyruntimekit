"""Tests for semantic typed identifiers."""

from dataclasses import FrozenInstanceError
from typing import Any, cast
from uuid import UUID

import pytest

from pyruntimekit.domain import ArtifactId, EventId, FailureId, RunId, WorkloadId

IdentifierType = (
    type[ArtifactId] | type[RunId] | type[WorkloadId] | type[FailureId] | type[EventId]
)

IDENTIFIER_TYPES: tuple[IdentifierType, ...] = (
    ArtifactId,
    RunId,
    WorkloadId,
    FailureId,
    EventId,
)


@pytest.mark.parametrize("identifier_type", IDENTIFIER_TYPES)
def test_new_identifier_is_valid_and_canonical(identifier_type: IdentifierType) -> None:
    identifier = identifier_type.new()

    parsed = UUID(identifier.value)

    assert type(identifier) is identifier_type
    assert identifier.value == str(parsed)
    assert str(identifier) == identifier.value


@pytest.mark.parametrize("identifier_type", IDENTIFIER_TYPES)
def test_identifier_can_be_reconstructed(identifier_type: IdentifierType) -> None:
    source = "550E8400E29B41D4A716446655440000"

    identifier = identifier_type.from_str(source)

    assert identifier.value == "550e8400-e29b-41d4-a716-446655440000"


def test_same_identifier_type_compares_and_hashes_by_value() -> None:
    value = "550e8400-e29b-41d4-a716-446655440000"

    first = RunId(value)
    second = RunId.from_str(value)

    assert first == second
    assert hash(first) == hash(second)
    assert {first, second} == {first}


def test_different_identifier_types_do_not_compare_equal() -> None:
    value = "550e8400-e29b-41d4-a716-446655440000"

    run_id: object = RunId(value)
    workload_id: object = WorkloadId(value)

    assert run_id != workload_id


def test_repr_exposes_semantic_type_and_stable_value() -> None:
    identifier = FailureId("550e8400-e29b-41d4-a716-446655440000")

    assert repr(identifier) == "FailureId('550e8400-e29b-41d4-a716-446655440000')"


def test_identifier_rejects_non_string_input() -> None:
    invalid_value = cast(Any, 123)

    with pytest.raises(TypeError, match="must be a string"):
        RunId(invalid_value)


def test_identifier_rejects_invalid_uuid_string() -> None:
    with pytest.raises(ValueError, match="valid UUID"):
        RunId("not-a-uuid")


def test_identifier_rejects_nil_uuid() -> None:
    with pytest.raises(ValueError, match="nil UUID"):
        EventId("00000000-0000-0000-0000-000000000000")


def test_identifier_is_immutable() -> None:
    identifier = WorkloadId("550e8400-e29b-41d4-a716-446655440000")

    with pytest.raises(FrozenInstanceError):
        identifier.__setattr__("_uuid", UUID("123e4567-e89b-12d3-a456-426614174000"))


def test_value_is_serialization_friendly_string() -> None:
    identifier = EventId("550e8400-e29b-41d4-a716-446655440000")

    payload: dict[str, str] = {"event_id": identifier.value}

    assert payload == {"event_id": "550e8400-e29b-41d4-a716-446655440000"}
