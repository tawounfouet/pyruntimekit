"""Synchronous submission orchestration for the first executable slice."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from pyruntimekit.application.runner import RunnerOutcome, SimpleRunner
from pyruntimekit.domain.ids import RunId
from pyruntimekit.domain.result import RunResult
from pyruntimekit.domain.run import Run
from pyruntimekit.executors.base import ResolvedWorkload
from pyruntimekit.kernel import (
    AdmitRun,
    CreateRun,
    KernelDecision,
    QueueRun,
    RuntimeKernel,
)

type SubmissionClock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class SubmissionOutcome:
    """Provisional synchronous submission result until RunHandle lands in PR 18."""

    created_decision: KernelDecision
    admitted_decision: KernelDecision
    queued_decision: KernelDecision
    runner_outcome: RunnerOutcome

    def __post_init__(self) -> None:
        run_ids = {
            self.created_decision.run.run_id,
            self.admitted_decision.run.run_id,
            self.queued_decision.run.run_id,
            self.runner_outcome.run.run_id,
        }
        if len(run_ids) != 1:
            raise ValueError("submission decisions must belong to the same Run")

    @property
    def run_id(self) -> RunId:
        """Return the logical Run identity."""
        return self.runner_outcome.run.run_id

    @property
    def run(self) -> Run:
        """Return the final Run produced synchronously by this bootstrap submission."""
        return self.runner_outcome.run

    @property
    def result(self) -> RunResult[object]:
        """Return the final logical RunResult."""
        return self.runner_outcome.result

    @property
    def decisions(self) -> tuple[KernelDecision, ...]:
        """Return all lifecycle decisions in causal order."""
        return (
            self.created_decision,
            self.admitted_decision,
            self.queued_decision,
            *self.runner_outcome.decisions,
        )


class SubmissionService:
    """Coordinate one local synchronous submission without owning lifecycle laws."""

    __slots__ = ("_clock", "_kernel", "_runner")

    def __init__(
        self,
        *,
        kernel: RuntimeKernel,
        runner: SimpleRunner,
        clock: SubmissionClock,
    ) -> None:
        if not isinstance(kernel, RuntimeKernel):
            raise TypeError("kernel must be a RuntimeKernel")
        if not isinstance(runner, SimpleRunner):
            raise TypeError("runner must be a SimpleRunner")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self._kernel = kernel
        self._runner = runner
        self._clock = clock

    def submit(
        self,
        workload: ResolvedWorkload,
        *,
        correlation_id: str | None = None,
        trace_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> SubmissionOutcome:
        """Create, admit, queue and synchronously execute one resolved Workload."""
        if not isinstance(workload, ResolvedWorkload):
            raise TypeError("workload must be a ResolvedWorkload")

        submission_metadata = {} if metadata is None else metadata
        created = self._kernel.create(
            CreateRun(
                workload_id=workload.workload_id,
                at=self._clock(),
                metadata=submission_metadata,
            )
        )
        admitted = self._kernel.apply(
            created.run,
            AdmitRun(at=self._clock()),
        )
        queued = self._kernel.apply(
            admitted.run,
            QueueRun(at=self._clock()),
        )
        effective_correlation_id = (
            queued.run.run_id.value if correlation_id is None else correlation_id
        )
        runner_outcome = self._runner.run(
            queued.run,
            workload,
            correlation_id=effective_correlation_id,
            trace_id=trace_id,
            metadata=submission_metadata,
        )

        return SubmissionOutcome(
            created_decision=created,
            admitted_decision=admitted,
            queued_decision=queued,
            runner_outcome=runner_outcome,
        )


__all__ = [
    "SubmissionClock",
    "SubmissionOutcome",
    "SubmissionService",
]
