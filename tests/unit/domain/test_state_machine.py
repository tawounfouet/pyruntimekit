"""Tests for the canonical Run lifecycle transition matrix and invariants."""

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from pyruntimekit.domain import (
    AttemptNumber,
    DomainInvariantError,
    InvalidRunTransitionError,
    RunId,
    RunState,
    allowed_next_states,
    is_transition_allowed,
    validate_finished_at_consistency,
    validate_next_attempt_number,
    validate_retry_identity,
    validate_terminal_evidence,
    validate_transition,
)

FINISHED_AT = datetime(2026, 10, 25, 18, 0, tzinfo=UTC)

EXPECTED_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset(
        {RunState.ADMITTED, RunState.CANCELLED, RunState.ABORTED}
    ),
    RunState.ADMITTED: frozenset(
        {RunState.QUEUED, RunState.CANCELLED, RunState.ABORTED}
    ),
    RunState.QUEUED: frozenset(
        {
            RunState.RUNNING,
            RunState.CANCELLED,
            RunState.TIMED_OUT,
            RunState.ABORTED,
        }
    ),
    RunState.RUNNING: frozenset(
        {
            RunState.SUCCEEDED,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.TIMED_OUT,
            RunState.SUSPENDED,
            RunState.LOST,
            RunState.RECOVERING,
            RunState.ABORTED,
        }
    ),
    RunState.RETRYING: frozenset(
        {
            RunState.QUEUED,
            RunState.CANCELLED,
            RunState.TIMED_OUT,
            RunState.ABORTED,
        }
    ),
    RunState.SUSPENDED: frozenset(
        {
            RunState.QUEUED,
            RunState.RECOVERING,
            RunState.CANCELLED,
            RunState.TIMED_OUT,
            RunState.ABORTED,
        }
    ),
    RunState.RECOVERING: frozenset(
        {
            RunState.QUEUED,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.TIMED_OUT,
            RunState.ABORTED,
        }
    ),
    RunState.LOST: frozenset(
        {
            RunState.RECOVERING,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.ABORTED,
        }
    ),
    RunState.SUCCEEDED: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.CANCELLED: frozenset(),
    RunState.TIMED_OUT: frozenset(),
    RunState.ABORTED: frozenset(),
}


@pytest.mark.parametrize("state", list(RunState))
def test_allowed_next_states_match_normative_matrix(state: RunState) -> None:
    assert allowed_next_states(state) == EXPECTED_TRANSITIONS[state]


@pytest.mark.parametrize("current_state", list(RunState))
@pytest.mark.parametrize("next_state", list(RunState))
def test_transition_matrix_is_exhaustive(
    current_state: RunState,
    next_state: RunState,
) -> None:
    expected = next_state in EXPECTED_TRANSITIONS[current_state]

    assert is_transition_allowed(current_state, next_state) is expected

    if expected:
        validate_transition(current_state, next_state)
    else:
        with pytest.raises(InvalidRunTransitionError) as exc_info:
            validate_transition(current_state, next_state)

        assert exc_info.value.current_state is current_state
        assert exc_info.value.next_state is next_state


@pytest.mark.parametrize(
    "terminal_state",
    [
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.TIMED_OUT,
        RunState.ABORTED,
    ],
)
def test_terminal_states_have_no_outgoing_transitions(
    terminal_state: RunState,
) -> None:
    assert terminal_state.is_terminal
    assert allowed_next_states(terminal_state) == frozenset()


@pytest.mark.parametrize("state", list(RunState))
def test_self_transitions_are_rejected(state: RunState) -> None:
    assert not is_transition_allowed(state, state)

    with pytest.raises(InvalidRunTransitionError):
        validate_transition(state, state)


def test_invalid_transition_error_has_stable_message() -> None:
    error = InvalidRunTransitionError(RunState.CREATED, RunState.RUNNING)

    assert str(error) == "invalid Run transition: CREATED -> RUNNING"
    assert isinstance(error, DomainInvariantError)


@pytest.mark.parametrize(
    ("previous", "proposed"),
    [
        (None, AttemptNumber(1)),
        (AttemptNumber(1), AttemptNumber(2)),
        (AttemptNumber(2), AttemptNumber(3)),
        (AttemptNumber(99), AttemptNumber(100)),
    ],
)
def test_attempt_progression_accepts_first_and_exact_next_number(
    previous: AttemptNumber | None,
    proposed: AttemptNumber,
) -> None:
    validate_next_attempt_number(previous, proposed)


@pytest.mark.parametrize(
    ("previous", "proposed"),
    [
        (None, AttemptNumber(2)),
        (AttemptNumber(1), AttemptNumber(1)),
        (AttemptNumber(1), AttemptNumber(3)),
        (AttemptNumber(3), AttemptNumber(2)),
    ],
)
def test_attempt_progression_rejects_skips_reuse_and_regression(
    previous: AttemptNumber | None,
    proposed: AttemptNumber,
) -> None:
    with pytest.raises(DomainInvariantError, match="invalid Attempt progression"):
        validate_next_attempt_number(previous, proposed)


def test_retry_identity_accepts_same_run_id() -> None:
    run_id = RunId.new()

    validate_retry_identity(run_id, run_id)


def test_retry_identity_rejects_new_run_id() -> None:
    with pytest.raises(DomainInvariantError, match="preserve RunId"):
        validate_retry_identity(RunId.new(), RunId.new())


@pytest.mark.parametrize(
    "state",
    [
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.TIMED_OUT,
        RunState.ABORTED,
    ],
)
def test_terminal_state_requires_finished_at(state: RunState) -> None:
    with pytest.raises(DomainInvariantError, match="requires finished_at"):
        validate_finished_at_consistency(state, None)


@pytest.mark.parametrize(
    "state",
    [
        RunState.CREATED,
        RunState.ADMITTED,
        RunState.QUEUED,
        RunState.RUNNING,
        RunState.RETRYING,
        RunState.SUSPENDED,
        RunState.RECOVERING,
        RunState.LOST,
    ],
)
def test_non_terminal_state_rejects_finished_at(state: RunState) -> None:
    with pytest.raises(DomainInvariantError, match="requires a terminal"):
        validate_finished_at_consistency(state, FINISHED_AT)


def test_finished_at_requires_timezone_awareness() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        validate_finished_at_consistency(
            RunState.SUCCEEDED,
            datetime(2026, 10, 25, 18, 0),
        )


def test_succeeded_evidence_requires_result_without_failure() -> None:
    validate_terminal_evidence(
        RunState.SUCCEEDED,
        result_present=True,
        failure_present=False,
        finished_at=FINISHED_AT,
    )

    with pytest.raises(DomainInvariantError, match="requires a result"):
        validate_terminal_evidence(
            RunState.SUCCEEDED,
            result_present=False,
            failure_present=False,
            finished_at=FINISHED_AT,
        )

    with pytest.raises(DomainInvariantError, match="must not carry a failure"):
        validate_terminal_evidence(
            RunState.SUCCEEDED,
            result_present=True,
            failure_present=True,
            finished_at=FINISHED_AT,
        )


def test_failed_evidence_requires_failure_without_success_result() -> None:
    validate_terminal_evidence(
        RunState.FAILED,
        result_present=False,
        failure_present=True,
        finished_at=FINISHED_AT,
    )

    with pytest.raises(DomainInvariantError, match="requires a failure"):
        validate_terminal_evidence(
            RunState.FAILED,
            result_present=False,
            failure_present=False,
            finished_at=FINISHED_AT,
        )

    with pytest.raises(DomainInvariantError, match="must not carry a success result"):
        validate_terminal_evidence(
            RunState.FAILED,
            result_present=True,
            failure_present=True,
            finished_at=FINISHED_AT,
        )


@pytest.mark.parametrize(
    "state",
    [RunState.CANCELLED, RunState.TIMED_OUT, RunState.ABORTED],
)
def test_other_terminal_states_only_require_finished_at_in_this_slice(
    state: RunState,
) -> None:
    validate_terminal_evidence(
        state,
        result_present=False,
        failure_present=False,
        finished_at=FINISHED_AT,
    )


@pytest.mark.parametrize(
    ("function_name", "args"),
    [
        ("allowed_next_states", (cast(Any, "CREATED"),)),
        ("is_transition_allowed", (cast(Any, "CREATED"), RunState.ADMITTED)),
        ("is_transition_allowed", (RunState.CREATED, cast(Any, "ADMITTED"))),
        ("validate_transition", (cast(Any, "CREATED"), RunState.ADMITTED)),
        ("validate_transition", (RunState.CREATED, cast(Any, "ADMITTED"))),
    ],
)
def test_transition_helpers_reject_non_run_state_values(
    function_name: str,
    args: tuple[object, ...],
) -> None:
    functions = {
        "allowed_next_states": allowed_next_states,
        "is_transition_allowed": is_transition_allowed,
        "validate_transition": validate_transition,
    }

    with pytest.raises(TypeError, match="RunState"):
        functions[function_name](*cast(Any, args))


def test_attempt_progression_rejects_invalid_types() -> None:
    with pytest.raises(TypeError, match="previous"):
        validate_next_attempt_number(
            cast(Any, 1),
            AttemptNumber(2),
        )

    with pytest.raises(TypeError, match="proposed"):
        validate_next_attempt_number(
            AttemptNumber(1),
            cast(Any, 2),
        )


def test_retry_identity_rejects_invalid_types() -> None:
    run_id = RunId.new()

    with pytest.raises(TypeError, match="original_run_id"):
        validate_retry_identity(cast(Any, run_id.value), run_id)

    with pytest.raises(TypeError, match="retry_run_id"):
        validate_retry_identity(run_id, cast(Any, run_id.value))


def test_terminal_evidence_rejects_non_boolean_presence_flags() -> None:
    with pytest.raises(TypeError, match="result_present"):
        validate_terminal_evidence(
            RunState.SUCCEEDED,
            result_present=cast(Any, 1),
            failure_present=False,
            finished_at=FINISHED_AT,
        )

    with pytest.raises(TypeError, match="failure_present"):
        validate_terminal_evidence(
            RunState.FAILED,
            result_present=False,
            failure_present=cast(Any, 1),
            finished_at=FINISHED_AT,
        )
