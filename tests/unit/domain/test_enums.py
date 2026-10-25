"""Tests for stable PyRuntimeKit domain enumerations."""

import json

import pytest

from pyruntimekit.domain import RunState


CANONICAL_RUN_STATES = (
    "CREATED",
    "ADMITTED",
    "QUEUED",
    "RUNNING",
    "RETRYING",
    "SUSPENDED",
    "RECOVERING",
    "LOST",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "TIMED_OUT",
    "ABORTED",
)

TERMINAL_RUN_STATES = {
    RunState.SUCCEEDED,
    RunState.FAILED,
    RunState.CANCELLED,
    RunState.TIMED_OUT,
    RunState.ABORTED,
}


def test_run_state_contains_all_canonical_values_in_declared_order() -> None:
    assert tuple(state.value for state in RunState) == CANONICAL_RUN_STATES


@pytest.mark.parametrize("state", TERMINAL_RUN_STATES)
def test_terminal_run_state_is_classified_as_terminal(state: RunState) -> None:
    assert state.is_terminal


@pytest.mark.parametrize(
    "state",
    tuple(state for state in RunState if state not in TERMINAL_RUN_STATES),
)
def test_non_terminal_run_state_is_not_classified_as_terminal(state: RunState) -> None:
    assert not state.is_terminal


@pytest.mark.parametrize("state", tuple(RunState))
def test_run_state_uses_explicit_stable_string_value(state: RunState) -> None:
    assert isinstance(state.value, str)
    assert state.value == state.name
    assert str(state) == state.value


def test_run_state_can_be_reconstructed_from_serialized_value() -> None:
    assert RunState("RUNNING") is RunState.RUNNING


def test_run_state_serializes_as_plain_json_string() -> None:
    payload = json.dumps({"state": RunState.SUCCEEDED})

    assert payload == '{"state": "SUCCEEDED"}'


def test_invalid_run_state_value_is_rejected() -> None:
    with pytest.raises(ValueError):
        RunState("UNKNOWN")
