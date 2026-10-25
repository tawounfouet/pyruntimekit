"""Tests for the initial SimpleRunner orchestration contract."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from pyruntimekit.application import (
    InvalidExecutorResultError,
    RunnerContractError,
    RunnerOutcome,
    SimpleRunner,
)
from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import (
    AttemptNumber,
    ExecutionResult,
    Failure,
    FailureCategory,
    FailureCode,
    FailureOrigin,
    FailureScope,
    FailureSeverity,
    InvalidRunTransitionError,
    Run,
    RunResult,
    RunState,
    Workload,
    WorkloadDescriptor,
    WorkloadId,
)
from pyruntimekit.kernel import (
    AdmitRun,
    CreateRun,
    QueueRun,
    RuntimeKernel,
)

T0 = datetime(2026, 10, 25, 22, 45, tzinfo=UTC)


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values: Iterator[datetime] = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


class RecordingExecutor:
    def __init__(self, result: ExecutionResult[object]) -> None:
        self.result = result
        self.calls: list[tuple[Workload, ExecutionContext]] = []

    def execute(
        self,
        workload: Workload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]:
        self.calls.append((workload, context))
        return self.result


class InvalidExecutor:
    def execute(self, workload: Workload, context: ExecutionContext) -> ExecutionResult[object]:
        return cast(Any, "not-an-execution-result")


class ExplodingExecutor:
    def execute(self, workload: Workload, context: ExecutionContext) -> ExecutionResult[object]:
        raise RuntimeError("backend raw error")


def _workload() -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference="tests.example",
        ),
        metadata={"workload": "meta"},
    )


def _queued_run(kernel: RuntimeKernel, workload: Workload) -> Run:
    created = kernel.create(
        CreateRun(
            at=T0,
            workload_id=workload.workload_id,
            metadata={"run": "meta"},
        )
    ).run
    admitted = kernel.apply(created, AdmitRun(at=T0 + timedelta(seconds=1))).run
    return kernel.apply(admitted, QueueRun(at=T0 + timedelta(seconds=2))).run


def _failure(at: datetime) -> Failure:
    return Failure.create(
        code=FailureCode("EXECUTOR.TEST"),
        category=FailureCategory.EXECUTION,
        origin=FailureOrigin.EXECUTOR,
        severity=FailureSeverity.ERROR,
        scope=FailureScope.ATTEMPT,
        message="executor failure",
        retryable=False,
        recoverable=False,
        occurred_at=at,
    )


def test_simple_runner_success_path_uses_kernel_and_context() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    queued = _queued_run(kernel, workload)
    execution = ExecutionResult[object].success(
        value={"answer": 42},
        metadata={"executor": "fake"},
    )
    executor = RecordingExecutor(execution)
    start_at = T0 + timedelta(seconds=3)
    complete_at = T0 + timedelta(seconds=4)
    runner = SimpleRunner(
        kernel=kernel,
        executor=executor,
        clock=SequenceClock(start_at, complete_at),
    )

    outcome = runner.run(
        queued,
        workload,
        correlation_id=" corr-42 ",
        trace_id=" trace-42 ",
        metadata={"tenant": "demo"},
    )

    assert isinstance(outcome, RunnerOutcome)
    assert outcome.started_decision.previous_state is RunState.QUEUED
    assert outcome.started_decision.next_state is RunState.RUNNING
    assert outcome.started_decision.run.updated_at == start_at
    assert outcome.context.run_id == queued.run_id
    assert outcome.context.workload_id == workload.workload_id
    assert outcome.context.attempt == AttemptNumber.first()
    assert outcome.context.correlation_id == "corr-42"
    assert outcome.context.trace_id == "trace-42"
    assert outcome.context.metadata_dict() == {"tenant": "demo"}

    assert executor.calls == [(workload, outcome.context)]
    assert outcome.execution_result is execution
    assert outcome.final_decision.previous_state is RunState.RUNNING
    assert outcome.final_decision.next_state is RunState.SUCCEEDED
    assert outcome.run.state is RunState.SUCCEEDED
    assert outcome.run.updated_at == complete_at
    assert outcome.result.succeeded
    assert outcome.result.value == {"answer": 42}
    assert outcome.result.metadata_dict() == {"executor": "fake"}
    assert outcome.decisions == (
        outcome.started_decision,
        outcome.final_decision,
    )


def test_simple_runner_failure_path_requests_fail_run() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    queued = _queued_run(kernel, workload)
    failure = _failure(T0 + timedelta(seconds=3))
    execution = ExecutionResult[object].from_failure(failure)
    executor = RecordingExecutor(execution)
    complete_at = T0 + timedelta(seconds=4)
    runner = SimpleRunner(
        kernel=kernel,
        executor=executor,
        clock=SequenceClock(T0 + timedelta(seconds=3), complete_at),
    )

    outcome = runner.run(
        queued,
        workload,
        correlation_id="corr",
    )

    assert outcome.run.state is RunState.FAILED
    assert outcome.result.failed
    assert outcome.result.failure is failure
    assert outcome.result.completed_at == complete_at
    assert outcome.final_decision.next_state is RunState.FAILED


def test_runner_does_not_mutate_input_run() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    queued = _queued_run(kernel, workload)
    original_snapshot = queued.snapshot()
    runner = SimpleRunner(
        kernel=kernel,
        executor=RecordingExecutor(ExecutionResult[object].success()),
        clock=SequenceClock(
            T0 + timedelta(seconds=3),
            T0 + timedelta(seconds=4),
        ),
    )

    outcome = runner.run(queued, workload, correlation_id="corr")

    assert queued.snapshot() == original_snapshot
    assert queued.state is RunState.QUEUED
    assert outcome.run is not queued
    assert outcome.run.run_id == queued.run_id


def test_runner_uses_next_attempt_number_for_retried_run() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    queued = _queued_run(kernel, workload)
    snapshot = queued.snapshot()
    retry_queued = Run.from_snapshot(
        type(snapshot)(
            schema_version=snapshot.schema_version,
            run_id=snapshot.run_id,
            workload_id=snapshot.workload_id,
            state=RunState.QUEUED.value,
            version=snapshot.version + 2,
            created_at=snapshot.created_at,
            updated_at=(T0 + timedelta(seconds=5)).isoformat().replace("+00:00", "Z"),
            current_attempt=1,
            metadata=snapshot.metadata,
        )
    )
    runner = SimpleRunner(
        kernel=kernel,
        executor=RecordingExecutor(ExecutionResult[object].success()),
        clock=SequenceClock(
            T0 + timedelta(seconds=6),
            T0 + timedelta(seconds=7),
        ),
    )

    outcome = runner.run(retry_queued, workload, correlation_id="corr")

    assert outcome.context.attempt == AttemptNumber(2)
    assert outcome.started_decision.run.current_attempt == AttemptNumber(2)


def test_runner_rejects_mismatched_workload_identity_before_execution() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    queued = _queued_run(kernel, workload)
    other = _workload()
    executor = RecordingExecutor(ExecutionResult[object].success())
    runner = SimpleRunner(
        kernel=kernel,
        executor=executor,
        clock=SequenceClock(T0 + timedelta(seconds=3)),
    )

    with pytest.raises(RunnerContractError, match="same workload_id"):
        runner.run(queued, other, correlation_id="corr")

    assert executor.calls == []


def test_runner_relies_on_kernel_to_reject_non_queued_run() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    created = kernel.create(CreateRun(at=T0, workload_id=workload.workload_id)).run
    runner = SimpleRunner(
        kernel=kernel,
        executor=RecordingExecutor(ExecutionResult[object].success()),
        clock=SequenceClock(T0 + timedelta(seconds=1)),
    )

    with pytest.raises(InvalidRunTransitionError):
        runner.run(created, workload, correlation_id="corr")


def test_runner_rejects_invalid_executor_result() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    queued = _queued_run(kernel, workload)
    runner = SimpleRunner(
        kernel=kernel,
        executor=InvalidExecutor(),
        clock=SequenceClock(
            T0 + timedelta(seconds=3),
            T0 + timedelta(seconds=4),
        ),
    )

    with pytest.raises(InvalidExecutorResultError, match="ExecutionResult"):
        runner.run(queued, workload, correlation_id="corr")


def test_runner_does_not_normalize_raw_executor_exceptions_yet() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    queued = _queued_run(kernel, workload)
    runner = SimpleRunner(
        kernel=kernel,
        executor=ExplodingExecutor(),
        clock=SequenceClock(T0 + timedelta(seconds=3)),
    )

    with pytest.raises(RuntimeError, match="backend raw error"):
        runner.run(queued, workload, correlation_id="corr")


def test_runner_validates_constructor_contract() -> None:
    kernel = RuntimeKernel()
    executor = RecordingExecutor(ExecutionResult[object].success())

    with pytest.raises(TypeError, match="RuntimeKernel"):
        SimpleRunner(
            kernel=cast(Any, object()),
            executor=executor,
            clock=SequenceClock(T0),
        )

    with pytest.raises(TypeError, match="clock must be callable"):
        SimpleRunner(
            kernel=kernel,
            executor=executor,
            clock=cast(Any, object()),
        )


def test_runner_validates_run_and_workload_types() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    executor = RecordingExecutor(ExecutionResult[object].success())
    runner = SimpleRunner(
        kernel=kernel,
        executor=executor,
        clock=SequenceClock(T0 + timedelta(seconds=1)),
    )

    with pytest.raises(TypeError, match="run must be a Run"):
        runner.run(cast(Any, object()), workload, correlation_id="corr")

    created = kernel.create(CreateRun(at=T0, workload_id=workload.workload_id)).run
    with pytest.raises(TypeError, match="workload must be a Workload"):
        runner.run(created, cast(Any, object()), correlation_id="corr")


def test_runner_outcome_requires_coherent_decisions_and_context() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    queued = _queued_run(kernel, workload)
    execution = ExecutionResult[object].success()
    runner = SimpleRunner(
        kernel=kernel,
        executor=RecordingExecutor(execution),
        clock=SequenceClock(
            T0 + timedelta(seconds=3),
            T0 + timedelta(seconds=4),
        ),
    )
    valid = runner.run(queued, workload, correlation_id="corr")

    other_workload = _workload()
    other_queued = _queued_run(kernel, other_workload)
    other = SimpleRunner(
        kernel=kernel,
        executor=RecordingExecutor(ExecutionResult[object].success()),
        clock=SequenceClock(
            T0 + timedelta(seconds=3),
            T0 + timedelta(seconds=4),
        ),
    ).run(other_queued, other_workload, correlation_id="other")

    with pytest.raises(RunnerContractError, match="same Run"):
        RunnerOutcome(
            started_decision=valid.started_decision,
            context=valid.context,
            execution_result=valid.execution_result,
            final_decision=other.final_decision,
        )


def test_successful_runner_result_is_logical_run_result() -> None:
    kernel = RuntimeKernel()
    workload = _workload()
    queued = _queued_run(kernel, workload)
    runner = SimpleRunner(
        kernel=kernel,
        executor=RecordingExecutor(ExecutionResult[object].success(value="done")),
        clock=SequenceClock(
            T0 + timedelta(seconds=3),
            T0 + timedelta(seconds=4),
        ),
    )

    result = runner.run(queued, workload, correlation_id="corr").result

    assert isinstance(result, RunResult)
    assert result.value == "done"
