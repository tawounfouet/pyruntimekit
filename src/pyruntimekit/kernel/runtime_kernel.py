"""Explicit lifecycle authority for PyRuntimeKit Runs."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from pyruntimekit.domain.enums import RunState
from pyruntimekit.domain.events import (
    DomainEvent,
    RunAborted,
    RunAdmitted,
    RunCancelled,
    RunCreated,
    RunFailed,
    RunQueued,
    RunStarted,
    RunSucceeded,
    RunTimedOut,
)
from pyruntimekit.domain.result import RunResult
from pyruntimekit.domain.run import Run

from .commands import (
    AbortRun,
    AdmitRun,
    CancelRun,
    CompleteRun,
    CreateRun,
    FailRun,
    QueueRun,
    RunCommand,
    StartRun,
    TimeoutRun,
)
from .decisions import KernelDecision
from .errors import InvalidKernelCommandError
from .transitions import transition_run


class RuntimeKernel:
    """Apply canonical Run lifecycle laws without performing execution or I/O."""

    def create(self, command: CreateRun) -> KernelDecision:
        """Create a Run and its version-zero RunCreated event."""
        if not isinstance(command, CreateRun):
            raise TypeError("command must be a CreateRun")

        run = Run.create(
            command.workload_id,
            run_id=command.run_id,
            created_at=command.at,
            metadata=command.metadata,
        )
        event = RunCreated.create(
            run_id=run.run_id,
            aggregate_version=run.version,
            occurred_at=command.at,
            payload={"workload_id": run.workload_id.value},
        )
        return KernelDecision(
            run=run,
            previous_state=None,
            next_state=RunState.CREATED,
            emitted_events=(event,),
        )

    def apply(self, run: Run, command: RunCommand) -> KernelDecision:
        """Apply one lifecycle command to an existing Run."""
        if not isinstance(run, Run):
            raise TypeError("run must be a Run")

        if isinstance(command, AdmitRun):
            return self._transition(
                run,
                RunState.ADMITTED,
                at=command.at,
                event_type=RunAdmitted,
            )

        if isinstance(command, QueueRun):
            return self._transition(
                run,
                RunState.QUEUED,
                at=command.at,
                event_type=RunQueued,
            )

        if isinstance(command, StartRun):
            return self._transition(
                run,
                RunState.RUNNING,
                at=command.at,
                event_type=RunStarted,
                attempt=command.attempt,
                payload={"attempt": command.attempt.value},
            )

        if isinstance(command, CompleteRun):
            return self._transition(
                run,
                RunState.SUCCEEDED,
                at=command.at,
                event_type=RunSucceeded,
                payload={
                    "artifact_count": len(command.result.artifacts),
                    "has_value": command.result.value is not None,
                },
                final_result=command.result,
            )

        if isinstance(command, FailRun):
            final_result = RunResult[object](
                completed_at=command.at,
                failure=command.failure,
            )
            return self._transition(
                run,
                RunState.FAILED,
                at=command.at,
                event_type=RunFailed,
                payload={
                    "failure_id": command.failure.failure_id.value,
                    "failure_code": command.failure.code.value,
                },
                final_result=final_result,
            )

        if isinstance(command, CancelRun):
            return self._transition(
                run,
                RunState.CANCELLED,
                at=command.at,
                event_type=RunCancelled,
            )

        if isinstance(command, TimeoutRun):
            return self._transition(
                run,
                RunState.TIMED_OUT,
                at=command.at,
                event_type=RunTimedOut,
            )

        if isinstance(command, AbortRun):
            return self._transition(
                run,
                RunState.ABORTED,
                at=command.at,
                event_type=RunAborted,
            )

        raise InvalidKernelCommandError(
            f"unsupported RuntimeKernel command: {type(command).__name__}"
        )

    @staticmethod
    def _transition(
        run: Run,
        next_state: RunState,
        *,
        at: datetime,
        event_type: type[DomainEvent],
        attempt: object | None = None,
        payload: Mapping[str, object] | None = None,
        final_result: RunResult[object] | None = None,
    ) -> KernelDecision:
        from pyruntimekit.domain.attempt import AttemptNumber

        typed_attempt: AttemptNumber | None
        if attempt is None:
            typed_attempt = None
        elif isinstance(attempt, AttemptNumber):
            typed_attempt = attempt
        else:
            raise TypeError("attempt must be an AttemptNumber or None")

        previous_state = run.state
        updated = transition_run(
            run,
            next_state,
            at=at,
            attempt=typed_attempt,
        )
        event = event_type.create(
            run_id=updated.run_id,
            aggregate_version=updated.version,
            occurred_at=updated.updated_at,
            payload={} if payload is None else payload,
        )
        return KernelDecision(
            run=updated,
            previous_state=previous_state,
            next_state=next_state,
            emitted_events=(event,),
            final_result=final_result,
        )


__all__ = ["RuntimeKernel"]
