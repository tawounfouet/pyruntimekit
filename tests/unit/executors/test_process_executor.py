"""Tests for the child-process Executor backend."""

from __future__ import annotations

import asyncio
import os
import pickle
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

import pyruntimekit.executors.process as process_module
from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import (
    AttemptNumber,
    ExecutionResult,
    FailureCategory,
    FailureOrigin,
    FailureScope,
    RunId,
    Workload,
    WorkloadDescriptor,
    WorkloadId,
)
from pyruntimekit.executors import (
    PROCESS_EXECUTOR_CAPABILITIES,
    ExecutorCapability,
    ProcessExecutorContract,
    ResolvedWorkload,
)
from pyruntimekit.executors.process import ProcessExecutor

NOW = datetime(2026, 10, 27, 18, 30, tzinfo=UTC)


def _workload() -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference="tests.process_executor:work",
        ),
    )


def _context(workload: Workload) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id="process-executor",
    )


def _requires_process_executor(executor: ProcessExecutorContract) -> None:
    assert executor.descriptor.kind == "process"


def _observe_child(received: ExecutionContext) -> object:
    return (
        os.getpid(),
        received.correlation_id,
        received.workload_id.value,
        received.attempt.value,
    )


def _return_existing_result(received: ExecutionContext) -> object:
    return ExecutionResult[object].success(
        value=received.correlation_id,
        metadata={"source": "process-child"},
    )


def _raise_value_error(received: ExecutionContext) -> object:
    raise ValueError(f"process bad input: {received.correlation_id}")


def _return_unpicklable_result(received: ExecutionContext) -> object:
    return lambda: received.correlation_id


def _sleep_then_return(received: ExecutionContext) -> object:
    time.sleep(0.12)
    return received.correlation_id


def _signal_then_sleep(received: ExecutionContext) -> object:
    Path(received.correlation_id).write_text("started", encoding="utf-8")
    time.sleep(0.15)
    return "finished"


def test_process_executor_structurally_satisfies_contract() -> None:
    executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)
    try:
        _requires_process_executor(executor)
        assert asyncio.iscoroutinefunction(executor.execute)
    finally:
        executor.close()


def test_process_executor_executes_in_child_process_with_exact_context() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        caller_pid = os.getpid()
        executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)

        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=_observe_child,
                ),
                context,
            )
        finally:
            executor.close()

        assert result.succeeded
        observation = cast(tuple[int, str, str, int], result.value)
        child_pid, correlation_id, workload_id, attempt = observation
        assert child_pid != caller_pid
        assert correlation_id == context.correlation_id
        assert workload_id == context.workload_id.value
        assert attempt == context.attempt.value

    asyncio.run(scenario())


def test_process_executor_preserves_existing_execution_result() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)

        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=_return_existing_result,
                ),
                context,
            )
        finally:
            executor.close()

        assert result.succeeded
        assert result.value == "process-executor"
        assert result.metadata_dict() == {"source": "process-child"}

    asyncio.run(scenario())


def test_process_executor_normalizes_ordinary_exception() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)

        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=_raise_value_error,
                ),
                context,
            )
        finally:
            executor.close()

        assert result.failed
        assert result.failure is not None
        failure = result.failure
        assert failure.code.value == "EXECUTOR.PROCESS.EXCEPTION"
        assert failure.category is FailureCategory.EXECUTION
        assert failure.origin is FailureOrigin.EXECUTOR
        assert failure.scope is FailureScope.ATTEMPT
        assert failure.occurred_at == NOW
        assert failure.message == "process bad input: process-executor"
        assert failure.cause is not None
        assert failure.cause.type_name == "ValueError"
        assert failure.cause.message == "process bad input: process-executor"
        assert failure.traceback_ref is None
        assert failure.to_dict()["metadata"] == {
            "executor": "process.default",
            "workload_kind": "python.callable",
        }

    asyncio.run(scenario())


def test_process_executor_capabilities_are_truthful_for_pr33() -> None:
    executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)
    try:
        descriptor = executor.descriptor
    finally:
        executor.close()

    assert descriptor.name == "process.default"
    assert descriptor.kind == "process"
    assert descriptor.capabilities == PROCESS_EXECUTOR_CAPABILITIES
    assert descriptor.capabilities.values == frozenset(
        {
            ExecutorCapability.TRUSTED_ONLY,
            ExecutorCapability.PROCESS_EXECUTION,
            ExecutorCapability.PROCESS_ISOLATION,
            ExecutorCapability.SERIALIZED_BOUNDARY,
            ExecutorCapability.BOUNDED_CAPACITY,
        }
    )
    assert not descriptor.capabilities.supports(ExecutorCapability.IN_PROCESS)
    assert not descriptor.capabilities.supports(ExecutorCapability.SHARED_MEMORY)
    assert descriptor.capabilities.supports(ExecutorCapability.SERIALIZED_BOUNDARY)
    assert descriptor.capabilities.supports(ExecutorCapability.BOUNDED_CAPACITY)


def test_process_executor_validates_contract_inputs() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)

        try:
            with pytest.raises(TypeError, match="ResolvedWorkload"):
                await executor.execute(cast(Any, object()), context)

            resolved = ResolvedWorkload(
                workload=workload,
                implementation=_observe_child,
            )
            with pytest.raises(TypeError, match="ExecutionContext"):
                await executor.execute(resolved, cast(Any, object()))
        finally:
            executor.close()

    asyncio.run(scenario())

    with pytest.raises(TypeError, match="max_workers"):
        ProcessExecutor(max_workers=cast(Any, True), clock=lambda: NOW)

    with pytest.raises(TypeError, match="max_workers"):
        ProcessExecutor(max_workers=cast(Any, "1"), clock=lambda: NOW)

    with pytest.raises(ValueError, match=">= 1"):
        ProcessExecutor(max_workers=0, clock=lambda: NOW)

    with pytest.raises(TypeError, match="max_in_flight"):
        ProcessExecutor(max_in_flight=cast(Any, True), clock=lambda: NOW)

    with pytest.raises(TypeError, match="max_in_flight"):
        ProcessExecutor(max_in_flight=cast(Any, "2"), clock=lambda: NOW)

    with pytest.raises(ValueError, match=">= 1"):
        ProcessExecutor(max_in_flight=0, clock=lambda: NOW)

    with pytest.raises(TypeError, match="clock must be callable"):
        ProcessExecutor(clock=cast(Any, object()))


def test_process_executor_rejects_context_for_other_workload() -> None:
    async def scenario() -> None:
        workload = _workload()
        other = _workload()
        executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)

        try:
            with pytest.raises(ValueError, match="share workload_id"):
                await executor.execute(
                    ResolvedWorkload(
                        workload=workload,
                        implementation=_observe_child,
                    ),
                    _context(other),
                )
        finally:
            executor.close()

    asyncio.run(scenario())


def test_process_executor_close_is_idempotent_and_prevents_reuse() -> None:
    async def scenario() -> None:
        workload = _workload()
        executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)

        executor.close()
        executor.close()

        with pytest.raises(RuntimeError, match="ProcessExecutor is closed"):
            await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=_observe_child,
                ),
                _context(workload),
            )

    asyncio.run(scenario())


def test_process_executor_rejects_unserializable_submission_before_execution() -> None:
    async def scenario() -> None:
        workload = _workload()
        executed = False

        def local_implementation(received: ExecutionContext) -> object:
            nonlocal executed
            executed = True
            return received.correlation_id

        executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)
        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=local_implementation,
                ),
                _context(workload),
            )
        finally:
            executor.close()

        assert not executed
        assert result.failed
        assert result.failure is not None
        failure = result.failure
        assert failure.code.value == "EXECUTOR.PROCESS.INPUT_SERIALIZATION"
        assert failure.message == "process submission is not serializable"
        assert failure.category is FailureCategory.EXECUTION
        assert failure.origin is FailureOrigin.EXECUTOR
        assert failure.scope is FailureScope.ATTEMPT
        assert failure.occurred_at == NOW
        assert failure.cause is not None
        assert failure.traceback_ref is None
        assert failure.to_dict()["metadata"] == {
            "executor": "process.default",
            "workload_kind": "python.callable",
            "boundary": "pickle",
        }

    asyncio.run(scenario())


def test_process_executor_normalizes_unserializable_child_result() -> None:
    async def scenario() -> None:
        workload = _workload()
        executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)

        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=_return_unpicklable_result,
                ),
                _context(workload),
            )
        finally:
            executor.close()

        assert result.failed
        assert result.failure is not None
        failure = result.failure
        assert failure.code.value == "EXECUTOR.PROCESS.RESULT_SERIALIZATION"
        assert failure.message == "process result is not serializable"
        assert failure.category is FailureCategory.EXECUTION
        assert failure.origin is FailureOrigin.EXECUTOR
        assert failure.scope is FailureScope.ATTEMPT
        assert failure.occurred_at == NOW
        assert failure.cause is not None
        assert failure.traceback_ref is None
        assert failure.to_dict()["metadata"] == {
            "executor": "process.default",
            "workload_kind": "python.callable",
            "boundary": "pickle",
        }

    asyncio.run(scenario())


def test_process_executor_normalizes_parent_result_deserialization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        workload = _workload()
        executor = ProcessExecutor(max_workers=1, clock=lambda: NOW)

        def fail_deserialization(payload: bytes) -> object:
            del payload
            raise pickle.UnpicklingError("corrupt result payload")

        monkeypatch.setattr(
            process_module,
            "deserialize_process_result",
            fail_deserialization,
        )

        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=_observe_child,
                ),
                _context(workload),
            )
        finally:
            executor.close()

        assert result.failed
        assert result.failure is not None
        failure = result.failure
        assert failure.code.value == "EXECUTOR.PROCESS.RESULT_DESERIALIZATION"
        assert failure.message == "process result could not be deserialized"
        assert failure.cause is not None
        assert failure.cause.type_name == "UnpicklingError"
        assert failure.cause.message == "corrupt result payload"
        assert failure.to_dict()["metadata"] == {
            "executor": "process.default",
            "workload_kind": "python.callable",
            "boundary": "pickle",
        }

    asyncio.run(scenario())


def test_process_executor_bounds_in_flight_submission_before_pool_queue() -> None:
    async def scenario() -> None:
        executor = ProcessExecutor(
            max_workers=1,
            max_in_flight=2,
            clock=lambda: NOW,
        )

        async def submit_one(label: str) -> ExecutionResult[object]:
            workload = _workload()
            context = ExecutionContext(
                run_id=RunId.new(),
                workload_id=workload.workload_id,
                attempt=AttemptNumber.first(),
                correlation_id=label,
            )
            return await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=_sleep_then_return,
                ),
                context,
            )

        tasks = [
            asyncio.create_task(submit_one("first")),
            asyncio.create_task(submit_one("second")),
            asyncio.create_task(submit_one("third")),
        ]

        try:
            for _ in range(300):
                if executor.current_load == 2:
                    break
                await asyncio.sleep(0.001)

            assert executor.max_in_flight == 2
            assert executor.current_load == 2
            assert not tasks[2].done()

            results = await asyncio.gather(*tasks)
            await asyncio.sleep(0)

            assert [result.value for result in results] == ["first", "second", "third"]
            assert executor.current_load == 0
        finally:
            executor.close()

    asyncio.run(scenario())


def test_process_capacity_survives_cancelled_await_until_backend_finishes(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        executor = ProcessExecutor(
            max_workers=1,
            max_in_flight=1,
            clock=lambda: NOW,
        )
        signal_path = tmp_path / "process-started"

        first_workload = _workload()
        first_context = ExecutionContext(
            run_id=RunId.new(),
            workload_id=first_workload.workload_id,
            attempt=AttemptNumber.first(),
            correlation_id=str(signal_path),
        )
        first_task = asyncio.create_task(
            executor.execute(
                ResolvedWorkload(
                    workload=first_workload,
                    implementation=_signal_then_sleep,
                ),
                first_context,
            )
        )

        try:
            for _ in range(500):
                if signal_path.exists():
                    break
                await asyncio.sleep(0.001)

            assert signal_path.exists()
            assert executor.current_load == 1

            first_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first_task

            assert executor.current_load == 1

            second_workload = _workload()
            second_task = asyncio.create_task(
                executor.execute(
                    ResolvedWorkload(
                        workload=second_workload,
                        implementation=_observe_child,
                    ),
                    _context(second_workload),
                )
            )
            await asyncio.sleep(0.02)

            assert not second_task.done()
            assert executor.current_load == 1

            second_result = await second_task
            await asyncio.sleep(0)

            assert second_result.succeeded
            assert executor.current_load == 0
        finally:
            executor.close()

    asyncio.run(scenario())
