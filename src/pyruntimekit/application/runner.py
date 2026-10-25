"""Initial application-layer Runner orchestration contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain.attempt import AttemptNumber
from pyruntimekit.domain.result import ExecutionResult, RunResult
from pyruntimekit.domain.run import Run
from pyruntimekit.domain.workload import Workload
from pyruntimekit.kernel import (
    CompleteRun,
    FailRun,
    KernelDecision,
    RuntimeKernel,
    StartRun,
)


class RunnerContractError(ValueError):
    """Raised when the Runner receives inconsistent orchestration inputs."""


class InvalidExecutorResultError(RunnerContractError):
    """Raised when a configured executor violates the result contract."""


class _ConfiguredExecutor(Protocol):
    """Temporary structural port until the public Executor contract lands in PR 16."""

    def execute(
        self,
        workload: Workload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]: ...


type RunnerClock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class RunnerOutcome:
    """Complete logical outcome of one local Runner orchestration."""

    started_decision: KernelDecision
    context: ExecutionContext
    execution_result: ExecutionResult[object]
    final_decision: KernelDecision

    def __post_init__(self) -> None:
        if self.started_decision.run.run_id != self.final_decision.run.run_id:
            raise RunnerContractError("Runner decisions must belong to the same Run")
        if self.context.run_id != self.final_decision.run.run_id:
            raise RunnerContractError("ExecutionContext must belong to the resulting Run")
        if self.context.attempt != self.started_decision.run.current_attempt:
            raise RunnerContractError("ExecutionContext attempt must equal the started Run attempt")
        if self.final_decision.final_result is None:
            raise RunnerContractError("Runner final decision requires a final RunResult")

    @property
    def run(self) -> Run:
        """Return the terminal Run produced by the orchestration."""
        return self.final_decision.run

    @property
    def result(self) -> RunResult[object]:
        """Return the logical final RunResult."""
        result = self.final_decision.final_result
        if result is None:
            raise RunnerContractError("Runner final decision requires a final RunResult")
        return result

    @property
    def decisions(self) -> tuple[KernelDecision, KernelDecision]:
        """Return lifecycle decisions in causal order."""
        return (self.started_decision, self.final_decision)


class Runner(Protocol):
    """Structural application contract for progressing one executable Run."""

    def run(
        self,
        run: Run,
        workload: Workload,
        *,
        correlation_id: str,
        trace_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> RunnerOutcome: ...


class SimpleRunner:
    """Synchronous local orchestrator for one configured Executor."""

    __slots__ = ("_clock", "_executor", "_kernel")

    def __init__(
        self,
        *,
        kernel: RuntimeKernel,
        executor: _ConfiguredExecutor,
        clock: RunnerClock,
    ) -> None:
        if not isinstance(kernel, RuntimeKernel):
            raise TypeError("kernel must be a RuntimeKernel")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self._kernel = kernel
        self._executor = executor
        self._clock = clock

    def run(
        self,
        run: Run,
        workload: Workload,
        *,
        correlation_id: str,
        trace_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> RunnerOutcome:
        """Progress one QUEUED Run through one execution attempt to terminal state."""
        if not isinstance(run, Run):
            raise TypeError("run must be a Run")
        if not isinstance(workload, Workload):
            raise TypeError("workload must be a Workload")
        if run.workload_id != workload.workload_id:
            raise RunnerContractError("Run and Workload must share the same workload_id")

        attempt = (
            AttemptNumber.first() if run.current_attempt is None else run.current_attempt.next()
        )
        started = self._kernel.apply(
            run,
            StartRun(
                at=self._clock(),
                attempt=attempt,
            ),
        )

        context = ExecutionContext(
            run_id=started.run.run_id,
            workload_id=started.run.workload_id,
            attempt=attempt,
            correlation_id=correlation_id,
            trace_id=trace_id,
            metadata={} if metadata is None else metadata,
        )

        execution_result = self._executor.execute(workload, context)
        if not isinstance(execution_result, ExecutionResult):
            raise InvalidExecutorResultError("configured executor must return an ExecutionResult")

        completed_at = self._clock()
        if execution_result.failed:
            failure = execution_result.failure
            if failure is None:
                raise InvalidExecutorResultError("failed ExecutionResult must contain a Failure")
            final = self._kernel.apply(
                started.run,
                FailRun(
                    at=completed_at,
                    failure=failure,
                ),
            )
        else:
            run_result = RunResult[object].success(
                completed_at=completed_at,
                value=execution_result.value,
                artifacts=execution_result.artifacts,
                metadata=execution_result.metadata_dict(),
            )
            final = self._kernel.apply(
                started.run,
                CompleteRun(result=run_result),
            )

        return RunnerOutcome(
            started_decision=started,
            context=context,
            execution_result=execution_result,
            final_decision=final,
        )


__all__ = [
    "InvalidExecutorResultError",
    "Runner",
    "RunnerClock",
    "RunnerContractError",
    "RunnerOutcome",
    "SimpleRunner",
]
