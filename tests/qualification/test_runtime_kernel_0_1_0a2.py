"""Milestone conformance suite for PyRuntimeKit 0.1.0a2."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from pyruntimekit import RunHandle, Runtime
from pyruntimekit.application import SimpleRunner, SubmissionService
from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import (
    FailureCategory,
    FailureOrigin,
    FailureScope,
    RunState,
    Workload,
    WorkloadDescriptor,
    WorkloadId,
)
from pyruntimekit.executors import ResolvedWorkload
from pyruntimekit.executors.inline import InlineExecutor
from pyruntimekit.kernel import RuntimeKernel

T0 = datetime(2026, 10, 26, 0, 55, tzinfo=UTC)


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values: Iterator[datetime] = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def _times(count: int, *, offset: int = 0) -> tuple[datetime, ...]:
    return tuple(T0 + timedelta(seconds=offset + index) for index in range(count))


def _workload(implementation: object) -> ResolvedWorkload:
    workload = Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference="tests.qualification:workload",
        ),
    )
    return ResolvedWorkload(
        workload=workload,
        implementation=cast(Any, implementation),
    )


def _service(clock: SequenceClock) -> SubmissionService:
    kernel = RuntimeKernel()
    runner = SimpleRunner(
        kernel=kernel,
        executor=InlineExecutor(clock=clock),
        clock=clock,
    )
    return SubmissionService(
        kernel=kernel,
        runner=runner,
        clock=clock,
    )


def _assert_decision_chain(
    outcome: object,
    *,
    expected_terminal: RunState,
    expected_terminal_event: str,
) -> None:
    decisions = outcome.decisions
    expected_states = [
        RunState.CREATED,
        RunState.ADMITTED,
        RunState.QUEUED,
        RunState.RUNNING,
        expected_terminal,
    ]
    expected_events = [
        "run.created",
        "run.admitted",
        "run.queued",
        "run.started",
        expected_terminal_event,
    ]

    assert [decision.next_state for decision in decisions] == expected_states
    assert [decision.run.version.value for decision in decisions] == [0, 1, 2, 3, 4]
    assert [decision.emitted_events[0].event_type for decision in decisions] == expected_events

    run_id = decisions[0].run.run_id
    for decision in decisions:
        assert len(decision.emitted_events) == 1
        event = decision.emitted_events[0]
        assert decision.run.run_id == run_id
        assert event.run_id == run_id
        assert event.aggregate_version == decision.run.version
        assert event.occurred_at == decision.run.updated_at


def test_successful_workload_qualifies_full_kernel_progression() -> None:
    clock = SequenceClock(*_times(5))
    resolved = _workload(lambda context: {"attempt": context.attempt.value})

    outcome = _service(clock).submit(
        resolved,
        correlation_id="qualification-success",
    )

    _assert_decision_chain(
        outcome,
        expected_terminal=RunState.SUCCEEDED,
        expected_terminal_event="run.succeeded",
    )
    assert outcome.result.succeeded
    assert outcome.result.value == {"attempt": 1}
    assert outcome.runner_outcome.context.attempt.value == 1
    assert outcome.runner_outcome.context.correlation_id == "qualification-success"


def test_failing_workload_qualifies_failure_normalization_and_kernel_progression() -> None:
    clock = SequenceClock(*_times(6))

    def fail(context: ExecutionContext) -> object:
        raise ValueError("qualification failure")

    outcome = _service(clock).submit(
        _workload(fail),
        correlation_id="qualification-failure",
    )

    _assert_decision_chain(
        outcome,
        expected_terminal=RunState.FAILED,
        expected_terminal_event="run.failed",
    )
    assert outcome.result.failed
    assert outcome.result.failure is not None
    failure = outcome.result.failure
    assert failure.code.value == "EXECUTOR.INLINE.EXCEPTION"
    assert failure.category is FailureCategory.EXECUTION
    assert failure.origin is FailureOrigin.EXECUTOR
    assert failure.scope is FailureScope.ATTEMPT
    assert failure.message == "qualification failure"
    assert failure.cause is not None
    assert failure.cause.type_name == "ValueError"
    assert failure.traceback_ref is None


def test_public_runtime_submit_and_run_handle_qualify_success_path() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(5)))

    handle = runtime.submit(lambda context: context.attempt.value)

    assert isinstance(handle, RunHandle)
    assert handle.status() is RunState.SUCCEEDED
    assert handle.result().succeeded
    assert handle.result().value == 1
    assert handle.wait() is handle.result()


def test_public_runtime_submit_and_run_handle_qualify_failure_path() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(6)))

    def fail(context: ExecutionContext) -> object:
        raise RuntimeError("public qualification failure")

    handle = runtime.submit(fail)

    assert handle.status() is RunState.FAILED
    result = handle.result()
    assert result.failed
    assert result.failure is not None
    assert result.failure.code.value == "EXECUTOR.INLINE.EXCEPTION"
    assert result.failure.origin is FailureOrigin.EXECUTOR
    assert handle.wait() is result


def test_public_runtime_rejects_invalid_submission_input() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(1)))

    with pytest.raises(TypeError, match="ResolvedWorkload or callable"):
        runtime.submit(cast(Any, object()))


def test_multiple_sequential_runs_remain_identity_and_result_isolated() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(15)))

    first = runtime.submit(lambda context: "first")

    def fail(context: ExecutionContext) -> object:
        raise ValueError("second failed")

    second = runtime.submit(fail)
    third = runtime.submit(lambda context: "third")

    assert len({first.run_id, second.run_id, third.run_id}) == 3

    assert first.status() is RunState.SUCCEEDED
    assert first.result().value == "first"

    assert second.status() is RunState.FAILED
    assert second.result().failure is not None
    assert second.result().failure.message == "second failed"

    assert third.status() is RunState.SUCCEEDED
    assert third.result().value == "third"

    assert first.result().value == "first"
    assert third.result().value == "third"
