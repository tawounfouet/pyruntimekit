"""Tests for SubmissionService lifecycle coordination."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from pyruntimekit.application import SimpleRunner, SubmissionOutcome, SubmissionService
from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import RunState, Workload, WorkloadDescriptor, WorkloadId
from pyruntimekit.executors import ResolvedWorkload
from pyruntimekit.executors.inline import InlineExecutor
from pyruntimekit.kernel import RuntimeKernel

T0 = datetime(2026, 10, 26, 0, 30, tzinfo=UTC)


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values: Iterator[datetime] = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def _resolved() -> ResolvedWorkload:
    workload = Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference="tests.submission:work",
        ),
    )
    return ResolvedWorkload(
        workload=workload,
        implementation=lambda context: context.correlation_id,
    )


def _service(clock: SequenceClock) -> SubmissionService:
    kernel = RuntimeKernel()
    executor = InlineExecutor(clock=clock)
    runner = SimpleRunner(kernel=kernel, executor=executor, clock=clock)
    return SubmissionService(kernel=kernel, runner=runner, clock=clock)


def test_submission_service_uses_kernel_for_full_progression() -> None:
    clock = SequenceClock(*(T0 + timedelta(seconds=i) for i in range(5)))
    service = _service(clock)

    outcome = service.submit(_resolved(), correlation_id="submission")

    assert [decision.next_state for decision in outcome.decisions] == [
        RunState.CREATED,
        RunState.ADMITTED,
        RunState.QUEUED,
        RunState.RUNNING,
        RunState.SUCCEEDED,
    ]
    assert [decision.run.version.value for decision in outcome.decisions] == [
        0,
        1,
        2,
        3,
        4,
    ]
    assert outcome.result.value == "submission"


def test_submission_service_defaults_correlation_to_run_id() -> None:
    clock = SequenceClock(*(T0 + timedelta(seconds=i) for i in range(5)))
    outcome = _service(clock).submit(_resolved())

    assert outcome.runner_outcome.context.correlation_id == outcome.run_id.value


def test_submission_service_validates_contract_inputs() -> None:
    kernel = RuntimeKernel()
    clock = SequenceClock(T0)
    runner = SimpleRunner(
        kernel=kernel,
        executor=InlineExecutor(clock=clock),
        clock=clock,
    )

    with pytest.raises(TypeError, match="RuntimeKernel"):
        SubmissionService(
            kernel=cast(Any, object()),
            runner=runner,
            clock=clock,
        )

    with pytest.raises(TypeError, match="SimpleRunner"):
        SubmissionService(
            kernel=kernel,
            runner=cast(Any, object()),
            clock=clock,
        )

    with pytest.raises(TypeError, match="clock must be callable"):
        SubmissionService(
            kernel=kernel,
            runner=runner,
            clock=cast(Any, object()),
        )

    service = SubmissionService(kernel=kernel, runner=runner, clock=clock)
    with pytest.raises(TypeError, match="ResolvedWorkload"):
        service.submit(cast(Any, object()))


def test_submission_outcome_rejects_mixed_run_decisions() -> None:
    first_clock = SequenceClock(*(T0 + timedelta(seconds=i) for i in range(5)))
    second_clock = SequenceClock(*(T0 + timedelta(seconds=10 + i) for i in range(5)))
    first = _service(first_clock).submit(_resolved())
    second = _service(second_clock).submit(_resolved())

    with pytest.raises(ValueError, match="same Run"):
        SubmissionOutcome(
            created_decision=first.created_decision,
            admitted_decision=first.admitted_decision,
            queued_decision=first.queued_decision,
            runner_outcome=second.runner_outcome,
        )


def test_submission_context_is_passed_to_callable() -> None:
    clock = SequenceClock(*(T0 + timedelta(seconds=i) for i in range(5)))
    observed: list[ExecutionContext] = []
    workload = Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference="tests.submission:observe",
        ),
    )
    def implementation(context: ExecutionContext) -> object:
        observed.append(context)
        return "ok"

    resolved = ResolvedWorkload(
        workload=workload,
        implementation=implementation,
    )

    outcome = _service(clock).submit(resolved, correlation_id="corr")

    assert observed == [outcome.runner_outcome.context]
