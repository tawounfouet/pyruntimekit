"""Tests for the thread-backed local Executor."""

from __future__ import annotations

import asyncio
import contextvars
import os
import threading
from datetime import UTC, datetime
from typing import Any, cast

import pytest

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
    THREAD_EXECUTOR_CAPABILITIES,
    ExecutorCapability,
    ResolvedWorkload,
    ThreadExecutorContract,
)
from pyruntimekit.executors.thread import ThreadExecutor

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def _workload() -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference="tests.thread_executor:work",
        ),
    )


def _context(workload: Workload) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id="thread-executor",
    )


def _requires_thread_executor(executor: ThreadExecutorContract) -> None:
    assert executor.descriptor.kind == "thread"


def test_thread_executor_structurally_satisfies_contract() -> None:
    executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)
    try:
        _requires_thread_executor(executor)
        assert asyncio.iscoroutinefunction(executor.execute)
    finally:
        executor.close()


def test_thread_executor_runs_sync_workload_in_different_thread_same_process() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        caller_pid = os.getpid()
        caller_thread = threading.get_ident()

        def implementation(received: ExecutionContext) -> object:
            return (
                os.getpid(),
                threading.get_ident(),
                threading.current_thread().name,
                received.correlation_id,
            )

        executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)
        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=implementation,
                ),
                context,
            )
        finally:
            executor.close()

        worker_pid, worker_thread, worker_name, correlation_id = cast(
            tuple[int, int, str, str],
            result.value,
        )
        assert worker_pid == caller_pid
        assert worker_thread != caller_thread
        assert worker_name.startswith("pyruntimekit-thread")
        assert correlation_id == "thread-executor"

    asyncio.run(scenario())


def test_thread_executor_preserves_existing_execution_result() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        expected = ExecutionResult[object].success(
            value="already-normalized",
            metadata={"source": "thread-workload"},
        )

        executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)
        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=lambda received: expected,
                ),
                context,
            )
        finally:
            executor.close()

        assert result is expected

    asyncio.run(scenario())


def test_thread_executor_normalizes_ordinary_exception() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)

        def implementation(received: ExecutionContext) -> object:
            raise ValueError("thread bad input")

        executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)
        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=implementation,
                ),
                context,
            )
        finally:
            executor.close()

        assert result.failed
        assert result.failure is not None
        failure = result.failure
        assert failure.code.value == "EXECUTOR.THREAD.EXCEPTION"
        assert failure.category is FailureCategory.EXECUTION
        assert failure.origin is FailureOrigin.EXECUTOR
        assert failure.scope is FailureScope.ATTEMPT
        assert failure.occurred_at == NOW
        assert failure.message == "thread bad input"
        assert failure.cause is not None
        assert failure.cause.type_name == "ValueError"
        assert failure.cause.message == "thread bad input"
        assert failure.traceback_ref is None
        assert failure.to_dict()["metadata"] == {
            "executor": "thread.default",
            "workload_kind": "python.callable",
        }

    asyncio.run(scenario())


def test_cancelling_await_does_not_claim_thread_termination() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        started = threading.Event()
        release = threading.Event()
        completed = threading.Event()

        def implementation(received: ExecutionContext) -> object:
            started.set()
            release.wait(timeout=2)
            completed.set()
            return "finished"

        executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)
        task = asyncio.create_task(
            executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=implementation,
                ),
                context,
            )
        )

        try:
            for _ in range(200):
                if started.is_set():
                    break
                await asyncio.sleep(0.001)

            assert started.is_set()
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

            assert not completed.is_set()
            release.set()

            for _ in range(200):
                if completed.is_set():
                    break
                await asyncio.sleep(0.001)

            assert completed.is_set()
        finally:
            release.set()
            executor.close()

    asyncio.run(scenario())


def test_thread_executor_does_not_propagate_contextvars_before_pr24() -> None:
    marker: contextvars.ContextVar[str] = contextvars.ContextVar(
        "thread_executor_marker",
        default="worker-default",
    )

    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        token = marker.set("caller-value")
        executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)

        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=lambda received: marker.get(),
                ),
                context,
            )
        finally:
            executor.close()
            marker.reset(token)

        assert result.value == "worker-default"

    asyncio.run(scenario())


def test_thread_executor_capabilities_are_truthful_for_pr23() -> None:
    executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)
    try:
        descriptor = executor.descriptor

        assert descriptor.name == "thread.default"
        assert descriptor.kind == "thread"
        assert descriptor.capabilities == THREAD_EXECUTOR_CAPABILITIES
        assert descriptor.capabilities.values == frozenset(
            {
                ExecutorCapability.IN_PROCESS,
                ExecutorCapability.SHARED_MEMORY,
                ExecutorCapability.TRUSTED_ONLY,
                ExecutorCapability.THREAD_EXECUTION,
            }
        )
        assert not descriptor.capabilities.supports(ExecutorCapability.ASYNC_EXECUTION)
        assert not descriptor.capabilities.supports(
            ExecutorCapability.THREAD_CONTEXT_PROPAGATION
        )
        assert not descriptor.capabilities.supports(ExecutorCapability.BOUNDED_CAPACITY)
    finally:
        executor.close()


def test_thread_executor_validates_constructor_and_contract_inputs() -> None:
    with pytest.raises(TypeError, match="max_workers"):
        ThreadExecutor(max_workers=cast(Any, True), clock=lambda: NOW)

    with pytest.raises(TypeError, match="max_workers"):
        ThreadExecutor(max_workers=cast(Any, "2"), clock=lambda: NOW)

    with pytest.raises(ValueError, match=">= 1"):
        ThreadExecutor(max_workers=0, clock=lambda: NOW)

    with pytest.raises(TypeError, match="clock must be callable"):
        ThreadExecutor(max_workers=1, clock=cast(Any, object()))

    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)

        try:
            with pytest.raises(TypeError, match="ResolvedWorkload"):
                await executor.execute(cast(Any, object()), context)

            resolved = ResolvedWorkload(
                workload=workload,
                implementation=lambda received: None,
            )
            with pytest.raises(TypeError, match="ExecutionContext"):
                await executor.execute(resolved, cast(Any, object()))
        finally:
            executor.close()

    asyncio.run(scenario())


def test_thread_executor_rejects_context_for_other_workload() -> None:
    async def scenario() -> None:
        workload = _workload()
        other = _workload()
        context = _context(other)
        executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)

        try:
            with pytest.raises(ValueError, match="share workload_id"):
                await executor.execute(
                    ResolvedWorkload(
                        workload=workload,
                        implementation=lambda received: None,
                    ),
                    context,
                )
        finally:
            executor.close()

    asyncio.run(scenario())


def test_close_is_idempotent_and_prevents_new_execution() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        resolved = ResolvedWorkload(
            workload=workload,
            implementation=lambda received: "unused",
        )
        executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)

        executor.close()
        executor.close()

        with pytest.raises(RuntimeError, match="closed"):
            await executor.execute(resolved, context)

    asyncio.run(scenario())
