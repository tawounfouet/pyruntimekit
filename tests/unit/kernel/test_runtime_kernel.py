"""Tests for RuntimeKernel lifecycle authority."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from pyruntimekit.domain import (
    AttemptNumber,
    DomainEvent,
    Failure,
    FailureCategory,
    FailureCode,
    FailureOrigin,
    FailureScope,
    FailureSeverity,
    InvalidRunTransitionError,
    Run,
    RunAborted,
    RunAdmitted,
    RunCancelled,
    RunCreated,
    RunFailed,
    RunQueued,
    RunResult,
    RunStarted,
    RunState,
    RunSucceeded,
    RunTimedOut,
    WorkloadId,
)
from pyruntimekit.kernel import (
    AbortRun,
    AdmitRun,
    CancelRun,
    CompleteRun,
    CreateRun,
    FailRun,
    InvalidKernelCommandError,
    KernelInvariantError,
    QueueRun,
    RuntimeKernel,
    StartRun,
    TimeoutRun,
    transition_run,
)

T0 = datetime(2026, 10, 25, 21, 0, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return T0 + timedelta(seconds=seconds)


def _failure(at: datetime) -> Failure:
    return Failure.create(
        code=FailureCode("EXECUTION.TEST"),
        category=FailureCategory.EXECUTION,
        origin=FailureOrigin.RUNTIME_KERNEL,
        severity=FailureSeverity.ERROR,
        scope=FailureScope.RUN,
        message="execution failed",
        retryable=False,
        recoverable=False,
        occurred_at=at,
    )


def _created(kernel: RuntimeKernel) -> Run:
    return kernel.create(
        CreateRun(
            at=T0,
            workload_id=WorkloadId.new(),
            metadata={"source": "test"},
        )
    ).run


def _queued(kernel: RuntimeKernel) -> Run:
    created = _created(kernel)
    admitted = kernel.apply(created, AdmitRun(at=_at(1))).run
    return kernel.apply(admitted, QueueRun(at=_at(2))).run


def _running(kernel: RuntimeKernel) -> Run:
    queued = _queued(kernel)
    return kernel.apply(
        queued,
        StartRun(at=_at(3), attempt=AttemptNumber.first()),
    ).run


def test_create_run_emits_version_zero_created_event() -> None:
    kernel = RuntimeKernel()
    workload_id = WorkloadId.new()

    decision = kernel.create(
        CreateRun(
            at=T0,
            workload_id=workload_id,
            metadata={"tenant": "demo"},
        )
    )

    assert decision.previous_state is None
    assert decision.next_state is RunState.CREATED
    assert decision.run.state is RunState.CREATED
    assert decision.run.version.value == 0
    assert decision.run.created_at == T0
    assert decision.run.updated_at == T0
    assert decision.run.workload_id == workload_id
    assert decision.run.metadata_dict() == {"tenant": "demo"}
    assert decision.final_result is None
    assert len(decision.emitted_events) == 1

    event = decision.emitted_events[0]
    assert isinstance(event, RunCreated)
    assert event.aggregate_version == decision.run.version
    assert event.occurred_at == T0
    assert event.payload_dict() == {"workload_id": workload_id.value}


def test_kernel_applies_happy_path_with_monotone_versions_and_events() -> None:
    kernel = RuntimeKernel()
    created = _created(kernel)

    admitted = kernel.apply(created, AdmitRun(at=_at(1)))
    queued = kernel.apply(admitted.run, QueueRun(at=_at(2)))
    started = kernel.apply(
        queued.run,
        StartRun(at=_at(3), attempt=AttemptNumber.first()),
    )
    result = RunResult[object].success(
        completed_at=_at(4),
        value=object(),
    )
    completed = kernel.apply(started.run, CompleteRun(result=result))

    expected = [
        (admitted, RunState.CREATED, RunState.ADMITTED, 1, RunAdmitted),
        (queued, RunState.ADMITTED, RunState.QUEUED, 2, RunQueued),
        (started, RunState.QUEUED, RunState.RUNNING, 3, RunStarted),
        (completed, RunState.RUNNING, RunState.SUCCEEDED, 4, RunSucceeded),
    ]

    for decision, previous, next_state, version, event_type in expected:
        assert decision.previous_state is previous
        assert decision.next_state is next_state
        assert decision.run.state is next_state
        assert decision.run.version.value == version
        event = decision.emitted_events[0]
        assert isinstance(event, event_type)
        assert event.aggregate_version == decision.run.version
        assert event.occurred_at == decision.run.updated_at

    assert started.run.current_attempt == AttemptNumber.first()
    assert started.emitted_events[0].payload_dict() == {"attempt": 1}
    assert completed.final_result is result
    assert completed.emitted_events[0].payload_dict() == {
        "artifact_count": 0,
        "has_value": True,
    }


def test_kernel_decision_does_not_mutate_input_run() -> None:
    kernel = RuntimeKernel()
    created = _created(kernel)

    decision = kernel.apply(created, AdmitRun(at=_at(1)))

    assert created.state is RunState.CREATED
    assert created.version.value == 0
    assert created.updated_at == T0
    assert decision.run is not created
    assert decision.run.run_id == created.run_id
    assert decision.run.state is RunState.ADMITTED
    assert decision.run.version.value == 1


def test_fail_run_produces_failed_result_and_failure_event() -> None:
    kernel = RuntimeKernel()
    running = _running(kernel)
    failure = _failure(_at(4))

    decision = kernel.apply(
        running,
        FailRun(at=_at(4), failure=failure),
    )

    assert decision.run.state is RunState.FAILED
    assert decision.final_result is not None
    assert decision.final_result.failed
    assert decision.final_result.failure is failure
    assert decision.final_result.completed_at == _at(4)

    event = decision.emitted_events[0]
    assert isinstance(event, RunFailed)
    assert event.payload_dict() == {
        "failure_id": failure.failure_id.value,
        "failure_code": failure.code.value,
    }


@pytest.mark.parametrize(
    ("command", "expected_state", "event_type"),
    [
        (CancelRun(at=_at(1)), RunState.CANCELLED, RunCancelled),
        (AbortRun(at=_at(1)), RunState.ABORTED, RunAborted),
    ],
)
def test_created_run_supports_terminal_control_commands(
    command: CancelRun | AbortRun,
    expected_state: RunState,
    event_type: type[DomainEvent],
) -> None:
    kernel = RuntimeKernel()
    created = _created(kernel)

    decision = kernel.apply(created, command)

    assert decision.run.state is expected_state
    assert isinstance(decision.emitted_events[0], event_type)
    assert decision.final_result is None


def test_timeout_run_from_queued_emits_timeout_event() -> None:
    kernel = RuntimeKernel()
    queued = _queued(kernel)

    decision = kernel.apply(queued, TimeoutRun(at=_at(3)))

    assert decision.run.state is RunState.TIMED_OUT
    assert isinstance(decision.emitted_events[0], RunTimedOut)


def test_invalid_transition_is_rejected_by_domain_matrix() -> None:
    kernel = RuntimeKernel()
    created = _created(kernel)

    with pytest.raises(InvalidRunTransitionError):
        kernel.apply(
            created,
            StartRun(at=_at(1), attempt=AttemptNumber.first()),
        )


def test_terminal_run_cannot_reopen() -> None:
    kernel = RuntimeKernel()
    running = _running(kernel)
    result = RunResult[object].success(completed_at=_at(4))
    succeeded = kernel.apply(running, CompleteRun(result=result)).run

    with pytest.raises(InvalidRunTransitionError):
        kernel.apply(succeeded, QueueRun(at=_at(5)))


def test_start_run_requires_first_or_next_attempt_number() -> None:
    kernel = RuntimeKernel()
    queued = _queued(kernel)

    with pytest.raises(ValueError, match="expected 1"):
        kernel.apply(
            queued,
            StartRun(at=_at(3), attempt=AttemptNumber(2)),
        )

    first_running = kernel.apply(
        queued,
        StartRun(at=_at(3), attempt=AttemptNumber(1)),
    ).run
    snapshot = first_running.snapshot()
    retry_queue = Run.from_snapshot(
        type(snapshot)(
            schema_version=snapshot.schema_version,
            run_id=snapshot.run_id,
            workload_id=snapshot.workload_id,
            state=RunState.QUEUED.value,
            version=snapshot.version + 2,
            created_at=snapshot.created_at,
            updated_at=_at(5).isoformat().replace("+00:00", "Z"),
            current_attempt=1,
            metadata=snapshot.metadata,
        )
    )

    second = kernel.apply(
        retry_queue,
        StartRun(at=_at(6), attempt=AttemptNumber(2)),
    )

    assert second.run.current_attempt == AttemptNumber(2)


def test_transition_engine_requires_attempt_for_running() -> None:
    kernel = RuntimeKernel()
    queued = _queued(kernel)

    with pytest.raises(KernelInvariantError, match="requires the next AttemptNumber"):
        transition_run(
            queued,
            RunState.RUNNING,
            at=_at(3),
        )


def test_transition_engine_rejects_attempt_for_non_running_transition() -> None:
    kernel = RuntimeKernel()
    created = _created(kernel)

    with pytest.raises(KernelInvariantError, match="only be supplied"):
        transition_run(
            created,
            RunState.ADMITTED,
            at=_at(1),
            attempt=AttemptNumber.first(),
        )


def test_transition_time_cannot_move_backwards() -> None:
    kernel = RuntimeKernel()
    created = _created(kernel)
    admitted = kernel.apply(created, AdmitRun(at=_at(2))).run

    with pytest.raises(ValueError, match="must not move backwards"):
        kernel.apply(admitted, QueueRun(at=_at(1)))


def test_kernel_rejects_invalid_runtime_values() -> None:
    kernel = RuntimeKernel()

    with pytest.raises(TypeError, match="CreateRun"):
        kernel.create(cast(Any, object()))

    with pytest.raises(TypeError, match="run must be a Run"):
        kernel.apply(cast(Any, object()), AdmitRun(at=T0))

    with pytest.raises(InvalidKernelCommandError, match="unsupported"):
        kernel.apply(_created(kernel), cast(Any, object()))
