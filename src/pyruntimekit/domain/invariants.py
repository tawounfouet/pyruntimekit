"""Pure reusable invariants for the Run lifecycle."""

from __future__ import annotations

from datetime import datetime
from types import MappingProxyType
from typing import Final

from .attempt import AttemptNumber
from .enums import RunState
from .exceptions import DomainInvariantError, InvalidRunTransitionError
from .ids import RunId
from .validation import normalize_aware_datetime


_ALLOWED_RUN_TRANSITIONS: Final = MappingProxyType(
    {
        RunState.CREATED: frozenset(
            {
                RunState.ADMITTED,
                RunState.CANCELLED,
                RunState.ABORTED,
            }
        ),
        RunState.ADMITTED: frozenset(
            {
                RunState.QUEUED,
                RunState.CANCELLED,
                RunState.ABORTED,
            }
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
)


def _require_run_state(value: RunState, *, field_name: str) -> RunState:
    if not isinstance(value, RunState):
        raise TypeError(f"{field_name} must be a RunState")
    return value


def allowed_next_states(state: RunState) -> frozenset[RunState]:
    """Return the canonical next states allowed from the current RunState."""
    current = _require_run_state(state, field_name="state")
    return _ALLOWED_RUN_TRANSITIONS[current]


def is_transition_allowed(current_state: RunState, next_state: RunState) -> bool:
    """Return whether the canonical lifecycle matrix allows the transition."""
    current = _require_run_state(current_state, field_name="current_state")
    next_ = _require_run_state(next_state, field_name="next_state")
    return next_ in _ALLOWED_RUN_TRANSITIONS[current]


def validate_transition(current_state: RunState, next_state: RunState) -> None:
    """Reject a transition that is not present in the canonical lifecycle matrix."""
    current = _require_run_state(current_state, field_name="current_state")
    next_ = _require_run_state(next_state, field_name="next_state")
    if next_ not in _ALLOWED_RUN_TRANSITIONS[current]:
        raise InvalidRunTransitionError(current, next_)


def validate_next_attempt_number(
    previous: AttemptNumber | None,
    proposed: AttemptNumber,
) -> None:
    """Require the first Attempt to be 1 and retries to advance exactly N -> N+1."""
    if previous is not None and not isinstance(previous, AttemptNumber):
        raise TypeError("previous must be an AttemptNumber or None")
    if not isinstance(proposed, AttemptNumber):
        raise TypeError("proposed must be an AttemptNumber")

    expected = AttemptNumber.first() if previous is None else previous.next()
    if proposed != expected:
        raise DomainInvariantError(
            f"invalid Attempt progression: expected {expected.value}, got {proposed.value}"
        )


def validate_retry_identity(original_run_id: RunId, retry_run_id: RunId) -> None:
    """Require retry to preserve the logical Run identity."""
    if not isinstance(original_run_id, RunId):
        raise TypeError("original_run_id must be a RunId")
    if not isinstance(retry_run_id, RunId):
        raise TypeError("retry_run_id must be a RunId")
    if retry_run_id != original_run_id:
        raise DomainInvariantError("retry must preserve RunId")


def validate_finished_at_consistency(
    state: RunState,
    finished_at: datetime | None,
) -> None:
    """Require finished_at exactly for terminal Run states."""
    current = _require_run_state(state, field_name="state")
    if finished_at is not None:
        normalize_aware_datetime(finished_at, field_name="finished_at")

    if finished_at is not None and not current.is_terminal:
        raise DomainInvariantError("finished_at requires a terminal RunState")
    if current.is_terminal and finished_at is None:
        raise DomainInvariantError("terminal RunState requires finished_at")


def validate_terminal_evidence(
    state: RunState,
    *,
    result_present: bool,
    failure_present: bool,
    finished_at: datetime | None,
) -> None:
    """Validate terminal result/failure evidence already modeled by the domain."""
    current = _require_run_state(state, field_name="state")
    if not isinstance(result_present, bool):
        raise TypeError("result_present must be a bool")
    if not isinstance(failure_present, bool):
        raise TypeError("failure_present must be a bool")

    validate_finished_at_consistency(current, finished_at)

    if current is RunState.SUCCEEDED:
        if not result_present:
            raise DomainInvariantError("SUCCEEDED Run requires a result")
        if failure_present:
            raise DomainInvariantError("SUCCEEDED Run must not carry a failure")
        return

    if current is RunState.FAILED:
        if not failure_present:
            raise DomainInvariantError("FAILED Run requires a failure")
        if result_present:
            raise DomainInvariantError("FAILED Run must not carry a success result")


__all__ = [
    "allowed_next_states",
    "is_transition_allowed",
    "validate_finished_at_consistency",
    "validate_next_attempt_number",
    "validate_retry_identity",
    "validate_terminal_evidence",
    "validate_transition",
]
