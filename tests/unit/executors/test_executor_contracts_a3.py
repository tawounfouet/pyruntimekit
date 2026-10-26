"""Contract evolution tests for the 0.1.0a3 executor milestone."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import AttemptNumber, ExecutionResult, RunId, Workload, WorkloadDescriptor, WorkloadId
from pyruntimekit.executors import (
    INLINE_EXECUTOR_CAPABILITIES,
    AsyncExecutorContract,
    Executor,
    ExecutorCapabilities,
    ExecutorCapability,
    ExecutorDescriptor,
    ResolvedAsyncWorkload,
    ResolvedWorkload,
)
from pyruntimekit.executors.inline import InlineExecutor

NOW = datetime(2026, 10, 26, 7, 20, tzinfo=UTC)


def _workload() -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference="tests.executor_contracts:work",
        ),
    )


def _context(workload: Workload) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id="contracts",
    )


def _requires_sync_executor(executor: Executor) -> None:
    assert executor.descriptor.kind


def _requires_async_executor(executor: AsyncExecutorContract) -> None:
    assert executor.descriptor.kind


class FakeAsyncExecutor:
    _DESCRIPTOR = ExecutorDescriptor(
        name="test.async",
        kind="async",
        capabilities=ExecutorCapabilities(
            frozenset(
                {
                    ExecutorCapability.IN_PROCESS,
                    ExecutorCapability.SHARED_MEMORY,
                    ExecutorCapability.TRUSTED_ONLY,
                    ExecutorCapability.ASYNC_EXECUTION,
                    ExecutorCapability.CONTEXTVARS_PROPAGATION,
                    ExecutorCapability.BOUNDED_CAPACITY,
                }
            )
        ),
    )

    @property
    def descriptor(self) -> ExecutorDescriptor:
        return self._DESCRIPTOR

    async def execute(
        self,
        workload: ResolvedAsyncWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]:
        value = await workload.implementation(context)
        return ExecutionResult[object].success(value=value)


def test_existing_sync_executor_contract_remains_compatible() -> None:
    executor = InlineExecutor(clock=lambda: NOW)

    _requires_sync_executor(executor)

    assert not inspect.iscoroutinefunction(executor.execute)


def test_async_executor_contract_is_awaitable_and_structural() -> None:
    executor = FakeAsyncExecutor()

    _requires_async_executor(executor)

    assert inspect.iscoroutinefunction(executor.execute)


def test_resolved_async_workload_preserves_domain_identity() -> None:
    workload = _workload()

    async def implementation(context: ExecutionContext) -> object:
        return context.correlation_id

    resolved = ResolvedAsyncWorkload(
        workload=workload,
        implementation=implementation,
    )

    assert resolved.workload is workload
    assert resolved.workload_id == workload.workload_id
    assert inspect.iscoroutinefunction(resolved.implementation)


def test_resolved_async_workload_validates_runtime_shape() -> None:
    workload = _workload()

    async def implementation(context: ExecutionContext) -> object:
        return None

    with pytest.raises(TypeError, match="workload must be a Workload"):
        ResolvedAsyncWorkload(
            workload=cast(Any, object()),
            implementation=implementation,
        )

    with pytest.raises(TypeError, match="implementation must be callable"):
        ResolvedAsyncWorkload(
            workload=workload,
            implementation=cast(Any, object()),
        )


def test_a3_capability_vocabulary_is_stable() -> None:
    assert {capability.value for capability in ExecutorCapability} == {
        "IN_PROCESS",
        "SHARED_MEMORY",
        "TRUSTED_ONLY",
        "ASYNC_EXECUTION",
        "THREAD_EXECUTION",
        "CONTEXTVARS_PROPAGATION",
        "THREAD_CONTEXT_PROPAGATION",
        "BOUNDED_CAPACITY",
    }


def test_inline_executor_does_not_gain_capabilities_by_vocabulary_expansion() -> None:
    assert INLINE_EXECUTOR_CAPABILITIES.values == frozenset(
        {
            ExecutorCapability.IN_PROCESS,
            ExecutorCapability.SHARED_MEMORY,
            ExecutorCapability.TRUSTED_ONLY,
        }
    )

    assert not INLINE_EXECUTOR_CAPABILITIES.supports(ExecutorCapability.ASYNC_EXECUTION)
    assert not INLINE_EXECUTOR_CAPABILITIES.supports(ExecutorCapability.THREAD_EXECUTION)
    assert not INLINE_EXECUTOR_CAPABILITIES.supports(
        ExecutorCapability.CONTEXTVARS_PROPAGATION
    )
    assert not INLINE_EXECUTOR_CAPABILITIES.supports(
        ExecutorCapability.THREAD_CONTEXT_PROPAGATION
    )
    assert not INLINE_EXECUTOR_CAPABILITIES.supports(ExecutorCapability.BOUNDED_CAPACITY)


def test_sync_and_async_resolved_workloads_remain_distinct_types() -> None:
    workload = _workload()

    sync_resolved = ResolvedWorkload(
        workload=workload,
        implementation=lambda context: context.correlation_id,
    )

    async def implementation(context: ExecutionContext) -> object:
        return context.correlation_id

    async_resolved = ResolvedAsyncWorkload(
        workload=workload,
        implementation=implementation,
    )

    assert type(sync_resolved) is ResolvedWorkload
    assert type(async_resolved) is ResolvedAsyncWorkload
    assert sync_resolved.workload_id == async_resolved.workload_id
