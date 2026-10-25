"""Composition test for SimpleRunner with the real InlineExecutor."""

from datetime import UTC, datetime, timedelta

from pyruntimekit.application import SimpleRunner
from pyruntimekit.domain import RunState, Workload, WorkloadDescriptor, WorkloadId
from pyruntimekit.executors import ResolvedWorkload
from pyruntimekit.executors.inline import InlineExecutor
from pyruntimekit.kernel import AdmitRun, CreateRun, QueueRun, RuntimeKernel

T0 = datetime(2026, 10, 25, 23, 58, tzinfo=UTC)


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def test_simple_runner_and_inline_executor_form_executable_slice() -> None:
    kernel = RuntimeKernel()
    workload = Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference="tests.integration.inline",
        ),
    )
    created = kernel.create(CreateRun(at=T0, workload_id=workload.workload_id)).run
    admitted = kernel.apply(
        created,
        AdmitRun(at=T0 + timedelta(seconds=1)),
    ).run
    queued = kernel.apply(
        admitted,
        QueueRun(at=T0 + timedelta(seconds=2)),
    ).run

    resolved = ResolvedWorkload(
        workload=workload,
        implementation=lambda context: {
            "correlation_id": context.correlation_id,
            "attempt": context.attempt.value,
        },
    )
    runner = SimpleRunner(
        kernel=kernel,
        executor=InlineExecutor(clock=lambda: T0 + timedelta(seconds=3)),
        clock=SequenceClock(
            T0 + timedelta(seconds=3),
            T0 + timedelta(seconds=4),
        ),
    )

    outcome = runner.run(
        queued,
        resolved,
        correlation_id="vertical-slice",
    )

    assert outcome.run.state is RunState.SUCCEEDED
    assert outcome.result.value == {
        "correlation_id": "vertical-slice",
        "attempt": 1,
    }
    assert outcome.context.workload_id == workload.workload_id
