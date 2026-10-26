"""Public Runtime.submit() tests through RunHandle."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from pyruntimekit import RunHandle, Runtime
from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import RunState, Workload, WorkloadDescriptor, WorkloadId
from pyruntimekit.executors import ResolvedWorkload

T0 = datetime(2026, 10, 26, 0, 20, tzinfo=UTC)


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values: Iterator[datetime] = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def _times(count: int, *, offset: int = 0) -> tuple[datetime, ...]:
    return tuple(T0 + timedelta(seconds=offset + index) for index in range(count))


def test_runtime_and_run_handle_are_publicly_importable() -> None:
    from pyruntimekit import RunHandle as PublicRunHandle
    from pyruntimekit import Runtime as PublicRuntime

    assert PublicRuntime is Runtime
    assert PublicRunHandle is RunHandle


def test_submit_callable_returns_run_handle() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(5)))

    handle = runtime.submit(
        lambda context: {
            "correlation_id": context.correlation_id,
            "attempt": context.attempt.value,
        }
    )

    assert isinstance(handle, RunHandle)
    assert handle.status() is RunState.SUCCEEDED
    assert handle.result().succeeded
    assert handle.result().value == {
        "correlation_id": handle.run_id.value,
        "attempt": 1,
    }
    assert handle.wait() is handle.result()


def test_callable_adaptation_remains_executable_through_handle() -> None:
    captured: list[ExecutionContext] = []

    def local_work(received: ExecutionContext) -> object:
        captured.append(received)
        return "done"

    runtime = Runtime(clock=SequenceClock(*_times(5)))
    handle = runtime.submit(local_work)

    assert handle.result().value == "done"
    assert len(captured) == 1
    assert captured[0].run_id == handle.run_id


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

    handle = runtime.submit(resolved)

    assert handle.status() is RunState.SUCCEEDED
    assert handle.result().value == workload.workload_id.value


def test_explicit_correlation_and_trace_are_visible_to_callable() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(5)))

    handle = runtime.submit(
        lambda context: (context.correlation_id, context.trace_id),
        correlation_id=" corr-explicit ",
        trace_id=" trace-explicit ",
    )

    assert handle.result().value == ("corr-explicit", "trace-explicit")


def test_submission_metadata_reaches_execution_context_defensively() -> None:
    metadata: dict[str, object] = {
        "tenant": "demo",
        "labels": ["alpha"],
    }
    runtime = Runtime(clock=SequenceClock(*_times(5)))

    handle = runtime.submit(
        lambda context: context.metadata_dict(),
        metadata=metadata,
    )

    cast(list[str], metadata["labels"]).append("changed")
    metadata["tenant"] = "mutated"

    assert handle.result().value == {
        "labels": ["alpha"],
        "tenant": "demo",
    }


def test_failing_callable_returns_failed_handle_result() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(6)))

    def fail(context: ExecutionContext) -> object:
        raise ValueError("public failure")

    handle = runtime.submit(fail)

    assert handle.status() is RunState.FAILED
    result = handle.result()
    assert result.failed
    assert result.failure is not None
    assert result.failure.code.value == "EXECUTOR.INLINE.EXCEPTION"
    assert result.failure.message == "public failure"
    assert result.failure.traceback_ref is None
    assert handle.wait() is result


def test_multiple_sequential_submissions_have_independent_handles() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(10)))

    first = runtime.submit(lambda context: "first")
    second = runtime.submit(lambda context: "second")

    assert first.run_id != second.run_id
    assert first.status() is RunState.SUCCEEDED
    assert second.status() is RunState.SUCCEEDED
    assert first.result().value == "first"
    assert second.result().value == "second"


def test_submit_rejects_non_callable_non_resolved_value() -> None:
    runtime = Runtime(clock=SequenceClock(*_times(1)))

    with pytest.raises(TypeError, match="ResolvedWorkload or callable"):
        runtime.submit(cast(Any, 42))


def test_runtime_validates_clock() -> None:
    with pytest.raises(TypeError, match="clock must be callable"):
        Runtime(clock=cast(Any, object()))
