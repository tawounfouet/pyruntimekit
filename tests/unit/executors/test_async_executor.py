"""Tests for the asynchronous in-process Executor backend."""

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
    ASYNC_EXECUTOR_CAPABILITIES,
    AsyncExecutorContract,
    ExecutorCapability,
    ResolvedAsyncWorkload,
)
from pyruntimekit.executors.async_ import AsyncExecutor

NOW = datetime(2026, 10, 27, 7, 0, tzinfo=UTC)


def _workload() -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.async_callable",
            reference="tests.async_executor:work",
        ),
    )


def _context(workload: Workload) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id="async-executor",
    )


def _requires_async_executor(executor: AsyncExecutorContract) -> None:
    assert executor.descriptor.kind == "async"


def test_async_executor_structurally_satisfies_contract() -> None:
    executor = AsyncExecutor(clock=lambda: NOW)

    _requires_async_executor(executor)

    assert asyncio.iscoroutinefunction(executor.execute)


def test_async_executor_executes_in_explicit_task() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        outer_task = asyncio.current_task()
        observed_task: asyncio.Task[object] | None = None

        async def implementation(received: ExecutionContext) -> object:
            nonlocal observed_task
            current = asyncio.current_task()
            assert current is not None
            observed_task = cast(asyncio.Task[object], current)
            return received.correlation_id

        result = await AsyncExecutor(clock=lambda: NOW).execute(
            ResolvedAsyncWorkload(
                workload=workload,
                implementation=implementation,
            ),
            context,
        )

        assert result.succeeded
        assert result.value == "async-executor"
        assert observed_task is not None
        assert observed_task is not outer_task
        assert observed_task.get_name().startswith(f"pyruntimekit:{context.run_id.value}:")

    asyncio.run(scenario())


def test_async_executor_preserves_existing_execution_result() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        expected = ExecutionResult[object].success(
            value="already-normalized",
            metadata={"source": "async-callable"},
        )

        async def implementation(received: ExecutionContext) -> object:
            return expected

        result = await AsyncExecutor(clock=lambda: NOW).execute(
            ResolvedAsyncWorkload(
                workload=workload,
                implementation=implementation,
            ),
            context,
        )

        assert result is expected

    asyncio.run(scenario())


def test_async_executor_normalizes_ordinary_exception() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)

        async def implementation(received: ExecutionContext) -> object:
            raise ValueError("async bad input")

        result = await AsyncExecutor(clock=lambda: NOW).execute(
            ResolvedAsyncWorkload(
                workload=workload,
                implementation=implementation,
            ),
            context,
        )

        assert result.failed
        assert result.failure is not None
        failure = result.failure
        assert failure.code.value == "EXECUTOR.ASYNC.EXCEPTION"
        assert failure.category is FailureCategory.EXECUTION
        assert failure.origin is FailureOrigin.EXECUTOR
        assert failure.scope is FailureScope.ATTEMPT
        assert failure.occurred_at == NOW
        assert failure.message == "async bad input"
        assert failure.cause is not None
        assert failure.cause.type_name == "ValueError"
        assert failure.cause.message == "async bad input"
        assert failure.traceback_ref is None
        assert failure.to_dict()["metadata"] == {
            "executor": "async.default",
            "workload_kind": "python.async_callable",
        }

    asyncio.run(scenario())


def test_async_executor_does_not_normalize_cancelled_error() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)

        async def implementation(received: ExecutionContext) -> object:
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await AsyncExecutor(clock=lambda: NOW).execute(
                ResolvedAsyncWorkload(
                    workload=workload,
                    implementation=implementation,
                ),
                context,
            )

    asyncio.run(scenario())


def test_async_executor_stays_in_same_process_and_thread() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        caller_pid = os.getpid()
        caller_thread = threading.get_ident()

        async def implementation(received: ExecutionContext) -> object:
            return (os.getpid(), threading.get_ident())

        result = await AsyncExecutor(clock=lambda: NOW).execute(
            ResolvedAsyncWorkload(
                workload=workload,
                implementation=implementation,
            ),
            context,
        )

        assert result.value == (caller_pid, caller_thread)

    asyncio.run(scenario())


def test_async_executor_propagates_and_isolates_contextvars() -> None:
    marker: contextvars.ContextVar[str] = contextvars.ContextVar(
        "async_executor_marker",
        default="root-default",
    )

    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        token = marker.set("caller-value")

        async def implementation(received: ExecutionContext) -> object:
            before = marker.get()
            marker.set("workload-value")
            await asyncio.sleep(0)
            return (before, marker.get())

        try:
            result = await AsyncExecutor(clock=lambda: NOW).execute(
                ResolvedAsyncWorkload(
                    workload=workload,
                    implementation=implementation,
                ),
                context,
            )

            assert result.value == ("caller-value", "workload-value")
            assert marker.get() == "caller-value"
        finally:
            marker.reset(token)

    asyncio.run(scenario())


def test_concurrent_async_executions_isolate_contextvars() -> None:
    marker: contextvars.ContextVar[str] = contextvars.ContextVar(
        "async_executor_isolation_marker",
        default="root-default",
    )

    async def scenario() -> None:
        executor = AsyncExecutor(clock=lambda: NOW)

        async def run_one(label: str) -> tuple[str, str]:
            workload = _workload()
            context = _context(workload)
            token = marker.set(label)

            async def implementation(received: ExecutionContext) -> object:
                before = marker.get()
                marker.set(f"{label}-inside")
                await asyncio.sleep(0)
                return (before, marker.get())

            try:
                result = await executor.execute(
                    ResolvedAsyncWorkload(
                        workload=workload,
                        implementation=implementation,
                    ),
                    context,
                )
                return cast(tuple[str, str], result.value)
            finally:
                marker.reset(token)

        first, second = await asyncio.gather(run_one("first"), run_one("second"))

        assert first == ("first", "first-inside")
        assert second == ("second", "second-inside")
        assert marker.get() == "root-default"

    asyncio.run(scenario())


def test_async_executor_capabilities_are_truthful_for_pr24() -> None:
    descriptor = AsyncExecutor(clock=lambda: NOW).descriptor

    assert descriptor.name == "async.default"
    assert descriptor.kind == "async"
    assert descriptor.capabilities == ASYNC_EXECUTOR_CAPABILITIES
    assert descriptor.capabilities.values == frozenset(
        {
            ExecutorCapability.IN_PROCESS,
            ExecutorCapability.SHARED_MEMORY,
            ExecutorCapability.TRUSTED_ONLY,
            ExecutorCapability.ASYNC_EXECUTION,
            ExecutorCapability.CONTEXTVARS_PROPAGATION,
        }
    )
    assert not descriptor.capabilities.supports(ExecutorCapability.THREAD_EXECUTION)
    assert descriptor.capabilities.supports(ExecutorCapability.CONTEXTVARS_PROPAGATION)
    assert not descriptor.capabilities.supports(ExecutorCapability.BOUNDED_CAPACITY)


def test_async_executor_validates_contract_inputs() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        executor = AsyncExecutor(clock=lambda: NOW)

        with pytest.raises(TypeError, match="ResolvedAsyncWorkload"):
            await executor.execute(cast(Any, object()), context)

        async def implementation(received: ExecutionContext) -> object:
            return None

        resolved = ResolvedAsyncWorkload(
            workload=workload,
            implementation=implementation,
        )
        with pytest.raises(TypeError, match="ExecutionContext"):
            await executor.execute(resolved, cast(Any, object()))

    asyncio.run(scenario())

    with pytest.raises(TypeError, match="clock must be callable"):
        AsyncExecutor(clock=cast(Any, object()))


def test_async_executor_rejects_context_for_other_workload() -> None:
    async def scenario() -> None:
        workload = _workload()
        other = _workload()
        context = _context(other)

        async def implementation(received: ExecutionContext) -> object:
            return None

        with pytest.raises(ValueError, match="share workload_id"):
            await AsyncExecutor(clock=lambda: NOW).execute(
                ResolvedAsyncWorkload(
                    workload=workload,
                    implementation=implementation,
                ),
                context,
            )

    asyncio.run(scenario())
