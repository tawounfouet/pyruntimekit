"""Standardized built-in Executor conformance suite for 0.1.0a3."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

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
    ExecutorCapability,
    ExecutorDescriptor,
    ResolvedAsyncWorkload,
    ResolvedWorkload,
)
from pyruntimekit.executors.async_ import AsyncExecutor
from pyruntimekit.executors.inline import InlineExecutor
from pyruntimekit.executors.thread import ThreadExecutor

NOW = datetime(2026, 10, 27, 12, 55, tzinfo=UTC)

type BackendName = Literal["inline", "async", "thread"]
type Behavior = Callable[[ExecutionContext], object]


@dataclass(frozen=True, slots=True)
class ExecutorCase:
    name: BackendName
    descriptor_name: str
    descriptor_kind: str
    failure_code: str
    expected_capabilities: frozenset[ExecutorCapability]


CASES = (
    ExecutorCase(
        name="inline",
        descriptor_name="inline.default",
        descriptor_kind="inline",
        failure_code="EXECUTOR.INLINE.EXCEPTION",
        expected_capabilities=frozenset(
            {
                ExecutorCapability.IN_PROCESS,
                ExecutorCapability.SHARED_MEMORY,
                ExecutorCapability.TRUSTED_ONLY,
            }
        ),
    ),
    ExecutorCase(
        name="async",
        descriptor_name="async.default",
        descriptor_kind="async",
        failure_code="EXECUTOR.ASYNC.EXCEPTION",
        expected_capabilities=frozenset(
            {
                ExecutorCapability.IN_PROCESS,
                ExecutorCapability.SHARED_MEMORY,
                ExecutorCapability.TRUSTED_ONLY,
                ExecutorCapability.ASYNC_EXECUTION,
                ExecutorCapability.CONTEXTVARS_PROPAGATION,
                ExecutorCapability.BOUNDED_CAPACITY,
            }
        ),
    ),
    ExecutorCase(
        name="thread",
        descriptor_name="thread.default",
        descriptor_kind="thread",
        failure_code="EXECUTOR.THREAD.EXCEPTION",
        expected_capabilities=frozenset(
            {
                ExecutorCapability.IN_PROCESS,
                ExecutorCapability.SHARED_MEMORY,
                ExecutorCapability.TRUSTED_ONLY,
                ExecutorCapability.THREAD_EXECUTION,
                ExecutorCapability.THREAD_CONTEXT_PROPAGATION,
                ExecutorCapability.BOUNDED_CAPACITY,
            }
        ),
    ),
)


def _workload(*, async_kind: bool = False) -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.async_callable" if async_kind else "python.callable",
            reference="tests.executor_conformance:work",
        ),
    )


def _context(workload: Workload) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id=f"conformance-{workload.workload_id.value}",
    )


async def _execute(
    case: ExecutorCase,
    behavior: Behavior,
    *,
    workload: Workload | None = None,
    context: ExecutionContext | None = None,
) -> ExecutionResult[object]:
    effective_workload = workload or _workload(async_kind=case.name == "async")
    effective_context = context or _context(effective_workload)

    if case.name == "inline":
        return InlineExecutor(clock=lambda: NOW).execute(
            ResolvedWorkload(
                workload=effective_workload,
                implementation=behavior,
            ),
            effective_context,
        )

    if case.name == "async":

        async def implementation(received: ExecutionContext) -> object:
            return behavior(received)

        return await AsyncExecutor(
            max_concurrency=2,
            clock=lambda: NOW,
        ).execute(
            ResolvedAsyncWorkload(
                workload=effective_workload,
                implementation=implementation,
            ),
            effective_context,
        )

    executor = ThreadExecutor(
        max_workers=1,
        max_in_flight=2,
        clock=lambda: NOW,
    )
    try:
        return await executor.execute(
            ResolvedWorkload(
                workload=effective_workload,
                implementation=behavior,
            ),
            effective_context,
        )
    finally:
        executor.close()


def _descriptor(case: ExecutorCase) -> ExecutorDescriptor:
    if case.name == "inline":
        return InlineExecutor(clock=lambda: NOW).descriptor
    if case.name == "async":
        return AsyncExecutor(max_concurrency=2, clock=lambda: NOW).descriptor

    executor = ThreadExecutor(
        max_workers=1,
        max_in_flight=2,
        clock=lambda: NOW,
    )
    try:
        return executor.descriptor
    finally:
        executor.close()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_executor_conformance_success_normalization(case: ExecutorCase) -> None:
    async def scenario() -> None:
        result = await _execute(
            case,
            lambda context: {
                "run_id": context.run_id.value,
                "attempt": context.attempt.value,
            },
        )

        assert result.succeeded
        assert result.value is not None
        assert result.failure is None

    asyncio.run(scenario())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_executor_conformance_preserves_execution_result(case: ExecutorCase) -> None:
    async def scenario() -> None:
        expected = ExecutionResult[object].success(
            value="normalized",
            metadata={"contract": "executor"},
        )

        result = await _execute(case, lambda context: expected)

        assert result is expected

    asyncio.run(scenario())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_executor_conformance_normalizes_ordinary_failure(case: ExecutorCase) -> None:
    async def scenario() -> None:
        def fail(context: ExecutionContext) -> object:
            raise ValueError(f"{case.name} conformance failure")

        result = await _execute(case, fail)

        assert result.failed
        assert result.failure is not None
        failure = result.failure
        assert failure.code.value == case.failure_code
        assert failure.category is FailureCategory.EXECUTION
        assert failure.origin is FailureOrigin.EXECUTOR
        assert failure.scope is FailureScope.ATTEMPT
        assert failure.message == f"{case.name} conformance failure"
        assert failure.cause is not None
        assert failure.cause.type_name == "ValueError"
        assert failure.traceback_ref is None

    asyncio.run(scenario())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_executor_conformance_delivers_exact_execution_context(case: ExecutorCase) -> None:
    async def scenario() -> None:
        workload = _workload(async_kind=case.name == "async")
        context = _context(workload)
        observed: list[ExecutionContext] = []

        def observe(received: ExecutionContext) -> object:
            observed.append(received)
            return received.correlation_id

        result = await _execute(
            case,
            observe,
            workload=workload,
            context=context,
        )

        assert result.value == context.correlation_id
        assert observed == [context]
        assert observed[0] is context

    asyncio.run(scenario())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_executor_conformance_rejects_workload_context_identity_mismatch(
    case: ExecutorCase,
) -> None:
    async def scenario() -> None:
        workload = _workload(async_kind=case.name == "async")
        other = _workload(async_kind=case.name == "async")
        context = _context(other)

        with pytest.raises(ValueError, match="share workload_id"):
            await _execute(
                case,
                lambda received: None,
                workload=workload,
                context=context,
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_executor_conformance_descriptor_and_capability_consistency(
    case: ExecutorCase,
) -> None:
    descriptor = _descriptor(case)

    assert descriptor.name == case.descriptor_name
    assert descriptor.kind == case.descriptor_kind
    assert descriptor.capabilities.values == case.expected_capabilities

    for capability in ExecutorCapability:
        assert descriptor.capabilities.supports(capability) is (
            capability in case.expected_capabilities
        )


def test_executor_conformance_timeout_is_explicitly_deferred() -> None:
    assert not hasattr(ExecutorCapability, "TIMEOUT")
    assert not hasattr(ExecutorCapability, "HARD_TIMEOUT")
