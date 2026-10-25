"""Immutable decisions returned by RuntimeKernel."""

from __future__ import annotations

from dataclasses import dataclass

from pyruntimekit.domain.enums import RunState
from pyruntimekit.domain.events import DomainEvent
from pyruntimekit.domain.invariants import (
    validate_terminal_evidence,
    validate_transition,
)
from pyruntimekit.domain.result import RunResult
from pyruntimekit.domain.run import Run, RunVersion

from .errors import KernelInvariantError


@dataclass(frozen=True, slots=True)
class KernelDecision:
    """Atomic logical outcome of one accepted Kernel command."""

    run: Run
    previous_state: RunState | None
    next_state: RunState
    emitted_events: tuple[DomainEvent, ...]
    final_result: RunResult[object] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run, Run):
            raise TypeError("run must be a Run")
        if self.previous_state is not None and not isinstance(self.previous_state, RunState):
            raise TypeError("previous_state must be a RunState or None")
        if not isinstance(self.next_state, RunState):
            raise TypeError("next_state must be a RunState")
        if not isinstance(self.emitted_events, tuple):
            raise TypeError("emitted_events must be a tuple")
        if not self.emitted_events:
            raise KernelInvariantError("KernelDecision requires at least one emitted event")
        if not all(isinstance(event, DomainEvent) for event in self.emitted_events):
            raise TypeError("emitted_events must contain only DomainEvent values")
        if self.final_result is not None and not isinstance(self.final_result, RunResult):
            raise TypeError("final_result must be a RunResult or None")

        if self.run.state is not self.next_state:
            raise KernelInvariantError("decision next_state must equal resulting Run.state")

        if self.previous_state is None:
            if self.next_state is not RunState.CREATED:
                raise KernelInvariantError("only Run creation may omit previous_state")
            if self.run.version != RunVersion.initial():
                raise KernelInvariantError("created Run must have RunVersion(0)")
        else:
            validate_transition(self.previous_state, self.next_state)

        for event in self.emitted_events:
            if event.run_id != self.run.run_id:
                raise KernelInvariantError("event run_id must equal resulting Run.run_id")
            if event.aggregate_version != self.run.version:
                raise KernelInvariantError(
                    "event aggregate_version must equal resulting Run.version"
                )
            if event.occurred_at != self.run.updated_at:
                raise KernelInvariantError("event occurred_at must equal resulting Run.updated_at")

        if self.next_state is RunState.SUCCEEDED:
            if self.final_result is None or self.final_result.failed:
                raise KernelInvariantError("SUCCEEDED decision requires successful RunResult")
            if self.final_result.completed_at != self.run.updated_at:
                raise KernelInvariantError(
                    "successful RunResult.completed_at must equal Run.updated_at"
                )
        elif self.next_state is RunState.FAILED:
            if self.final_result is None or self.final_result.succeeded:
                raise KernelInvariantError("FAILED decision requires failed RunResult")
            if self.final_result.completed_at != self.run.updated_at:
                raise KernelInvariantError(
                    "failed RunResult.completed_at must equal Run.updated_at"
                )
        elif self.final_result is not None:
            raise KernelInvariantError(
                "final_result is only valid for SUCCEEDED or FAILED decisions"
            )

        validate_terminal_evidence(
            self.next_state,
            result_present=self.next_state is RunState.SUCCEEDED
            and self.final_result is not None,
            failure_present=self.next_state is RunState.FAILED
            and self.final_result is not None
            and self.final_result.failure is not None,
            finished_at=self.run.updated_at if self.next_state.is_terminal else None,
        )


__all__ = ["KernelDecision"]
