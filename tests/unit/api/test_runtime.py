"""Public Runtime.submit() vertical-slice tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from pyruntimekit import Runtime
from pyruntimekit.application import SubmissionOutcome
from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import (
    RunState,
    Workload,
    WorkloadDescriptor,
    WorkloadId,
)
from pyruntimekit.executors import ResolvedWorkload

T0 = datetime(2026, 10, 26, 0, 20, tzinfo=UTC)


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values: Iterator[datetime] = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def _times(count: int, *, offset: int = 0) -> tuple[datetime, ...]:
    return tuple(T0 + timedelta(seconds=offset + index) for index in range(count))


def test_runtime_is_publicly_importable() -> None:
    from pyruntimekit import Runtime as PublicRuntime

    assert PublicRuntime is Runtime


def test_submit_callable_executes_complete_vertical_slice() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(5)))

    submission = runtime.submit(
        lambda context: {
            "correlation_id": context.correlation_id,
            "attempt": context.attempt.value,
        }
    )

    assert isinstance(submission, SubmissionOutcome)
    assert submission.run.state is RunState.SUCCEEDED
    assert submission.result.succeeded
    assert submission.result.value == {
        "correlation_id": submission.run_id.value,
        "attempt": 1,
    }
    assert submission.runner_outcome.context.correlation_id == submission.run_id.value
    assert [decision.next_state for decision in submission.decisions] == [
        RunState.CREATED,
        RunState.ADMITTED,
        RunState.QUEUED,
        RunState.RUNNING,
        RunState.SUCCEEDED,
    ]


def test_callable_adaptation_creates_python_callable_descriptor() -> None:
    captured: list[ExecutionContext] = []

    def local_work(received: ExecutionContext) -> object:
        captured.append(received)
        return "done"

    runtime = Runtime(clock=SequenceClock(*_times(5)))
    submission = runtime.submit(local_work)

    assert submission.result.value == "done"
    assert captured == [submission.runner_outcome.context]
    assert submission.runner_outcome.context.workload_id == submission.run.workload_id


def test_submit_accepts_pre_resolved_workload_without_replacing_identity() -> None:
    workload = Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference="tests.runtime:resolved",
        ),
    )
    resolved = ResolvedWorkload(
        workload=workload,
        implementation=lambda context: context.workload_id.value,
    )
    runtime = Runtime(clock=SequenceClock(*_times(5)))

    submission = runtime.submit(resolved)

    assert submission.run.workload_id == workload.workload_id
    assert submission.result.value == workload.workload_id.value


def test_explicit_correlation_and_trace_are_normalized() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(5)))

    submission = runtime.submit(
        lambda context: (context.correlation_id, context.trace_id),
        correlation_id=" corr-explicit ",
        trace_id=" trace-explicit ",
    )

    assert submission.result.value == ("corr-explicit", "trace-explicit")
    assert submission.runner_outcome.context.correlation_id == "corr-explicit"
    assert submission.runner_outcome.context.trace_id == "trace-explicit"


def test_submission_metadata_reaches_run_and_execution_context_defensively() -> None:
    metadata: dict[str, object] = {
        "tenant": "demo",
        "labels": ["alpha"],
    }
    runtime = Runtime(clock=SequenceClock(*_times(5)))

    submission = runtime.submit(
        lambda context: context.metadata_dict(),
        metadata=metadata,
    )

    cast(list[str], metadata["labels"]).append("changed")
    metadata["tenant"] = "mutated"

    assert submission.run.metadata_dict() == {
        "labels": ["alpha"],
        "tenant": "demo",
    }
    assert submission.runner_outcome.context.metadata_dict() == {
        "labels": ["alpha"],
        "tenant": "demo",
    }
    assert submission.result.value == {
        "labels": ["alpha"],
        "tenant": "demo",
    }


def test_failing_callable_becomes_failed_run_with_normalized_failure() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(6)))

    def fail(context: ExecutionContext) -> object:
        raise ValueError("public failure")

    submission = runtime.submit(fail)

    assert submission.run.state is RunState.FAILED
    assert submission.result.failed
    assert submission.result.failure is not None
    assert submission.result.failure.code.value == "EXECUTOR.INLINE.EXCEPTION"
    assert submission.result.failure.message == "public failure"
    assert submission.result.failure.traceback_ref is None
    assert [decision.next_state for decision in submission.decisions] == [
        RunState.CREATED,
        RunState.ADMITTED,
        RunState.QUEUED,
        RunState.RUNNING,
        RunState.FAILED,
    ]


def test_multiple_sequential_submissions_have_distinct_run_ids() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(10)))

    first = runtime.submit(lambda context: "first")
    second = runtime.submit(lambda context: "second")

    assert first.run_id != second.run_id
    assert first.result.value == "first"
    assert second.result.value == "second"


def test_submit_rejects_non_callable_non_resolved_value() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(1)))

    with pytest.raises(TypeError, match="ResolvedWorkload or callable"):
        runtime.submit(cast(Any, 42))


def test_runtime_validates_clock() -> None:
    with pytest.raises(TypeError, match="clock must be callable"):
        Runtime(clock=cast(Any, object()))
