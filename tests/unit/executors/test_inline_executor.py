"""Tests for InlineExecutor and executor contracts."""

from __future__ import annotations

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
    Workload,
    WorkloadDescriptor,
    WorkloadId,
)
from pyruntimekit.executors import (
    INLINE_EXECUTOR_CAPABILITIES,
    ExecutorCapabilities,
    ExecutorCapability,
    ExecutorDescriptor,
    ResolvedWorkload,
)
from pyruntimekit.executors.inline import InlineExecutor
from pyruntimekit.domain import RunId

NOW = datetime(2026, 10, 25, 23, 55, tzinfo=UTC)


def _workload() -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference="tests.inline",
        ),
    )


def _context(workload: Workload) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id="corr",
    )


def test_resolved_workload_keeps_domain_and_live_callable_separate() -> None:
    workload = _workload()

    resolved = ResolvedWorkload(
        workload=workload,
        implementation=lambda context: context.correlation_id,
    )

    assert resolved.workload is workload
    assert resolved.workload_id == workload.workload_id
    assert callable(resolved.implementation)


def test_resolved_workload_validates_inputs() -> None:
    workload = _workload()

    with pytest.raises(TypeError, match="workload must be a Workload"):
        ResolvedWorkload(
            workload=cast(Any, object()),
            implementation=lambda context: None,
        )

    with pytest.raises(TypeError, match="implementation must be callable"):
        ResolvedWorkload(
            workload=workload,
            implementation=cast(Any, object()),
        )


def test_capabilities_are_explicit_and_immutable() -> None:
    assert INLINE_EXECUTOR_CAPABILITIES.supports(ExecutorCapability.IN_PROCESS)
    assert INLINE_EXECUTOR_CAPABILITIES.supports(ExecutorCapability.SHARED_MEMORY)
    assert INLINE_EXECUTOR_CAPABILITIES.supports(ExecutorCapability.TRUSTED_ONLY)

    with pytest.raises(TypeError, match="frozenset"):
        ExecutorCapabilities(values=cast(Any, set()))

    with pytest.raises(TypeError, match="ExecutorCapability"):
        ExecutorCapabilities(values=cast(Any, frozenset({"IN_PROCESS"})))

    with pytest.raises(TypeError, match="ExecutorCapability"):
        INLINE_EXECUTOR_CAPABILITIES.supports(cast(Any, "IN_PROCESS"))


def test_executor_descriptor_normalizes_and_validates() -> None:
    descriptor = ExecutorDescriptor(
        name=" inline.default ",
        kind=" inline ",
        capabilities=INLINE_EXECUTOR_CAPABILITIES,
    )

    assert descriptor.name == "inline.default"
    assert descriptor.kind == "inline"

    with pytest.raises(TypeError, match="ExecutorCapabilities"):
        ExecutorDescriptor(
            name="x",
            kind="inline",
            capabilities=cast(Any, object()),
        )


def test_inline_executor_executes_once_and_passes_exact_context() -> None:
    workload = _workload()
    context = _context(workload)
    calls: list[ExecutionContext] = []

    def implementation(received: ExecutionContext) -> object:
        calls.append(received)
        return {"ok": True}

    executor = InlineExecutor(clock=lambda: NOW)
    result = executor.execute(
        ResolvedWorkload(workload=workload, implementation=implementation),
        context,
    )

    assert calls == [context]
    assert result.succeeded
    assert result.value == {"ok": True}


def test_inline_executor_preserves_existing_execution_result() -> None:
    workload = _workload()
    context = _context(workload)
    expected = ExecutionResult[object].success(
        value="already-normalized",
        metadata={"source": "callable"},
    )

    result = InlineExecutor(clock=lambda: NOW).execute(
        ResolvedWorkload(
            workload=workload,
            implementation=lambda received: expected,
        ),
        context,
    )

    assert result is expected


def test_inline_executor_normalizes_exception_to_failure() -> None:
    workload = _workload()
    context = _context(workload)

    def implementation(received: ExecutionContext) -> object:
        raise ValueError("bad input")

    result = InlineExecutor(clock=lambda: NOW).execute(
        ResolvedWorkload(workload=workload, implementation=implementation),
        context,
    )

    assert result.failed
    assert result.failure is not None
    failure = result.failure
    assert failure.code.value == "EXECUTOR.INLINE.EXCEPTION"
    assert failure.category is FailureCategory.EXECUTION
    assert failure.origin is FailureOrigin.EXECUTOR
    assert failure.scope is FailureScope.ATTEMPT
    assert failure.occurred_at == NOW
    assert failure.message == "bad input"
    assert failure.cause is not None
    assert failure.cause.type_name == "ValueError"
    assert failure.cause.message == "bad input"
    assert failure.traceback_ref is None
    assert failure.to_dict()["metadata"] == {
        "executor": "inline.default",
        "workload_kind": "python.callable",
    }


def test_inline_executor_does_not_swallow_base_exception() -> None:
    workload = _workload()
    context = _context(workload)

    class FatalSignal(BaseException):
        pass

    def implementation(received: ExecutionContext) -> object:
        raise FatalSignal()

    with pytest.raises(FatalSignal):
        InlineExecutor(clock=lambda: NOW).execute(
            ResolvedWorkload(workload=workload, implementation=implementation),
            context,
        )


def test_inline_executor_runs_in_same_process_and_thread() -> None:
    workload = _workload()
    context = _context(workload)
    caller_pid = os.getpid()
    caller_thread = threading.get_ident()

    def implementation(received: ExecutionContext) -> object:
        return (os.getpid(), threading.get_ident())

    result = InlineExecutor(clock=lambda: NOW).execute(
        ResolvedWorkload(workload=workload, implementation=implementation),
        context,
    )

    assert result.value == (caller_pid, caller_thread)


def test_inline_executor_descriptor_is_truthful() -> None:
    descriptor = InlineExecutor(clock=lambda: NOW).descriptor

    assert descriptor.name == "inline.default"
    assert descriptor.kind == "inline"
    assert descriptor.capabilities == INLINE_EXECUTOR_CAPABILITIES


def test_inline_executor_validates_contract_inputs() -> None:
    workload = _workload()
    context = _context(workload)
    executor = InlineExecutor(clock=lambda: NOW)

    with pytest.raises(TypeError, match="ResolvedWorkload"):
        executor.execute(cast(Any, object()), context)

    resolved = ResolvedWorkload(
        workload=workload,
        implementation=lambda received: None,
    )
    with pytest.raises(TypeError, match="ExecutionContext"):
        executor.execute(resolved, cast(Any, object()))

    with pytest.raises(TypeError, match="clock must be callable"):
        InlineExecutor(clock=cast(Any, object()))


def test_inline_executor_rejects_context_for_other_workload() -> None:
    workload = _workload()
    other = _workload()
    context = _context(other)

    with pytest.raises(ValueError, match="share workload_id"):
        InlineExecutor(clock=lambda: NOW).execute(
            ResolvedWorkload(
                workload=workload,
                implementation=lambda received: None,
            ),
            context,
        )
