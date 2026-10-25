"""Pure transition application owned by the RuntimeKernel layer."""

from __future__ import annotations

from datetime import datetime

from pyruntimekit.domain.attempt import AttemptNumber
from pyruntimekit.domain.enums import RunState
from pyruntimekit.domain.invariants import (
    validate_next_attempt_number,
    validate_transition,
)
from pyruntimekit.domain.run import Run

from .errors import KernelInvariantError


def transition_run(
    run: Run,
    next_state: RunState,
    *,
    at: datetime,
    attempt: AttemptNumber | None = None,
) -> Run:
    """Apply one already-requested lifecycle transition to a new Run representation."""
    if not isinstance(run, Run):
        raise TypeError("run must be a Run")
    if not isinstance(next_state, RunState):
        raise TypeError("next_state must be a RunState")

    validate_transition(run.state, next_state)

    if next_state is RunState.RUNNING:
        if attempt is None:
            raise KernelInvariantError("RUNNING transition requires the next AttemptNumber")
        validate_next_attempt_number(run.current_attempt, attempt)
        next_attempt = attempt
    else:
        if attempt is not None:
            raise KernelInvariantError("attempt may only be supplied for RUNNING transition")
        next_attempt = run.current_attempt

    return run._evolve_lifecycle(
        state=next_state,
        updated_at=at,
        current_attempt=next_attempt,
    )


__all__ = ["transition_run"]
