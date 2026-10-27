"""Conformance matrix for PyRuntimeKit 0.1.0a4 isolated executors."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, cast

import pytest

import pyruntimekit
import pyruntimekit.executors as executors
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
    SUBPROCESS_EXECUTOR_CAPABILITIES,
    ExecutorCapability,
    ProcessExecutorContract,
    ResolvedSubprocessWorkload,
    ResolvedWorkload,
    SubprocessCommand,
    SubprocessExecutorContract,
)
from pyruntimekit.executors.process import ProcessExecutor
from pyruntimekit.executors.subprocess import SubprocessExecutor

type BackendKind = Literal["process", "subprocess"]
type ExecuteOne = Callable[[str], Awaitable[ExecutionResult[object]]]


@dataclass(frozen=True, slots=True)
class ConformanceCase:
    kind: BackendKind
    descriptor_name: str
    execution_capability: ExecutorCapability
    serialized_boundary: bool


CASES = (
    ConformanceCase(
        kind="process",
        descriptor_name="process.default",
        execution_capability=ExecutorCapability.PROCESS_EXECUTION,
        serialized_boundary=True,
    ),
    ConformanceCase(
        kind="subprocess",
        descriptor_name="subprocess.default",
        execution_capability=ExecutorCapability.SUBPROCESS_EXECUTION,
        serialized_boundary=False,
    ),
)


def _workload(kind: str) -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind=kind,
            reference="tests.executor_conformance_a4:work",
        ),
    )


def _context(workload: Workload, label: str) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id=label,
    )


def _process_identity(received: ExecutionContext) -> object:
    return (os.getpid(), received.correlation_id)


def _process_sleep(received: ExecutionContext) -> object:
    time.sleep(0.08)
    return received.correlation_id


def _process_failure(received: ExecutionContext) -> object:
    raise RuntimeError(f"process-conformance:{received.correlation_id}")


def _process_unpicklable_result(received: ExecutionContext) -> object:
    return lambda: received.correlation_id


def _requires_process_contract(executor: ProcessExecutorContract) -> None:
    assert executor.descriptor.kind == "process"


def _requires_subprocess_contract(executor: SubprocessExecutorContract) -> None:
    assert executor.descriptor.kind == "subprocess"


async def _assert_bounded_backpressure(
    execute_one: ExecuteOne,
    current_load: Callable[[], int],
    close: Callable[[], None],
) -> None:
    first = asyncio.create_task(execute_one("first"))
    second = asyncio.create_task(execute_one("second"))

    try:
        for _ in range(300):
            if current_load() == 1:
                break
            await asyncio.sleep(0.001)

        assert current_load() == 1
        assert not second.done()

        first_result, second_result = await asyncio.gather(first, second)
        await asyncio.sleep(0)

        assert first_result.succeeded
        assert second_result.succeeded
        assert current_load() == 0
    finally:
        close()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.kind)
def test_a4_isolated_executor_descriptor_and_capability_conformance(
    case: ConformanceCase,
) -> None:
    if case.kind == "process":
        executor = ProcessExecutor(max_workers=1, max_in_flight=1)
        try:
            descriptor = executor.descriptor
            capabilities = PROCESS_EXECUTOR_CAPABILITIES
        finally:
            executor.close()
    else:
        executor = SubprocessExecutor(max_concurrency=1)
        descriptor = executor.descriptor
        capabilities = SUBPROCESS_EXECUTOR_CAPABILITIES

    assert descriptor.name == case.descriptor_name
    assert descriptor.kind == case.kind
    assert descriptor.capabilities == capabilities
    assert capabilities.supports(ExecutorCapability.TRUSTED_ONLY)
    assert capabilities.supports(ExecutorCapability.PROCESS_ISOLATION)
    assert capabilities.supports(ExecutorCapability.BOUNDED_CAPACITY)
    assert capabilities.supports(case.execution_capability)
    assert capabilities.supports(ExecutorCapability.SERIALIZED_BOUNDARY) is (
        case.serialized_boundary
    )
    assert not capabilities.supports(ExecutorCapability.IN_PROCESS)
    assert not capabilities.supports(ExecutorCapability.SHARED_MEMORY)


def test_a4_isolated_executors_structurally_satisfy_distinct_contracts() -> None:
    process_executor = ProcessExecutor(max_workers=1, max_in_flight=1)
    subprocess_executor = SubprocessExecutor(max_concurrency=1)

    try:
        _requires_process_contract(process_executor)
        _requires_subprocess_contract(subprocess_executor)
        assert asyncio.iscoroutinefunction(process_executor.execute)
        assert asyncio.iscoroutinefunction(subprocess_executor.execute)
    finally:
        process_executor.close()
        subprocess_executor.close()


@pytest.mark.parametrize("kind", ("process", "subprocess"))
def test_a4_isolated_executors_reject_context_for_another_workload(
    kind: BackendKind,
) -> None:
    async def scenario() -> None:
        workload = _workload("python.callable" if kind == "process" else "os.command")
        other = _workload("python.callable" if kind == "process" else "os.command")
        context = _context(other, "mismatch")

        if kind == "process":
            executor = ProcessExecutor(max_workers=1, max_in_flight=1)
            try:
                with pytest.raises(ValueError, match="share workload_id"):
                    await executor.execute(
                        ResolvedWorkload(
                            workload=workload,
                            implementation=_process_identity,
                        ),
                        context,
                    )
            finally:
                executor.close()
            return

        executor = SubprocessExecutor(max_concurrency=1)
        try:
            with pytest.raises(ValueError, match="share workload_id"):
                await executor.execute(
                    ResolvedSubprocessWorkload(
                        workload=workload,
                        command=SubprocessCommand(argv=(sys.executable, "-c", "print('unused')")),
                    ),
                    context,
                )
        finally:
            executor.close()

    asyncio.run(scenario())


def test_a4_isolated_executor_success_paths_return_normalized_results() -> None:
    async def scenario() -> None:
        process_workload = _workload("python.callable")
        process_executor = ProcessExecutor(max_workers=1, max_in_flight=1)
        try:
            process_result = await process_executor.execute(
                ResolvedWorkload(
                    workload=process_workload,
                    implementation=_process_identity,
                ),
                _context(process_workload, "process-success"),
            )
        finally:
            process_executor.close()

        subprocess_workload = _workload("os.command")
        subprocess_executor = SubprocessExecutor(max_concurrency=1)
        try:
            subprocess_result = await subprocess_executor.execute(
                ResolvedSubprocessWorkload(
                    workload=subprocess_workload,
                    command=SubprocessCommand(
                        argv=(
                            sys.executable,
                            "-c",
                            "print('subprocess-success')",
                        )
                    ),
                ),
                _context(subprocess_workload, "subprocess-success"),
            )
        finally:
            subprocess_executor.close()

        assert process_result.succeeded
        assert process_result.failure is None
        child_pid, correlation_id = cast(tuple[int, str], process_result.value)
        assert child_pid != os.getpid()
        assert correlation_id == "process-success"

        assert subprocess_result.succeeded
        assert subprocess_result.failure is None
        assert subprocess_result.exit_code == 0
        assert subprocess_result.stdout == "subprocess-success\n"
        assert subprocess_result.stderr == ""

    asyncio.run(scenario())


def test_a4_isolated_executor_failures_are_normalized_and_safe() -> None:
    async def scenario() -> None:
        process_workload = _workload("python.callable")
        process_executor = ProcessExecutor(max_workers=1, max_in_flight=1)
        try:
            process_result = await process_executor.execute(
                ResolvedWorkload(
                    workload=process_workload,
                    implementation=_process_failure,
                ),
                _context(process_workload, "failure"),
            )
        finally:
            process_executor.close()

        subprocess_workload = _workload("os.command")
        subprocess_executor = SubprocessExecutor(max_concurrency=1)
        try:
            subprocess_result = await subprocess_executor.execute(
                ResolvedSubprocessWorkload(
                    workload=subprocess_workload,
                    command=SubprocessCommand(
                        argv=(
                            sys.executable,
                            "-c",
                            "import sys; print('bad', file=sys.stderr); raise SystemExit(9)",
                        )
                    ),
                ),
                _context(subprocess_workload, "failure"),
            )
        finally:
            subprocess_executor.close()

        assert process_result.failed
        assert process_result.failure is not None
        assert process_result.failure.code.value == "EXECUTOR.PROCESS.EXCEPTION"
        assert process_result.failure.category is FailureCategory.EXECUTION
        assert process_result.failure.origin is FailureOrigin.EXECUTOR
        assert process_result.failure.scope is FailureScope.ATTEMPT
        assert process_result.failure.traceback_ref is None

        assert subprocess_result.failed
        assert subprocess_result.failure is not None
        assert subprocess_result.failure.code.value == "EXECUTOR.SUBPROCESS.NONZERO_EXIT"
        assert subprocess_result.failure.category is FailureCategory.EXECUTION
        assert subprocess_result.failure.origin is FailureOrigin.EXECUTOR
        assert subprocess_result.failure.scope is FailureScope.ATTEMPT
        assert subprocess_result.failure.traceback_ref is None
        assert subprocess_result.exit_code == 9
        assert subprocess_result.stderr == "bad\n"

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ("process", "subprocess"))
def test_a4_isolated_executor_bounded_capacity_applies_backpressure(
    kind: BackendKind,
) -> None:
    async def scenario() -> None:
        if kind == "process":
            process_executor = ProcessExecutor(
                max_workers=1,
                max_in_flight=1,
            )

            async def execute_process(label: str) -> ExecutionResult[object]:
                workload = _workload("python.callable")
                return await process_executor.execute(
                    ResolvedWorkload(
                        workload=workload,
                        implementation=_process_sleep,
                    ),
                    _context(workload, label),
                )

            def process_load() -> int:
                return process_executor.current_load

            await _assert_bounded_backpressure(
                execute_process,
                process_load,
                process_executor.close,
            )
            return

        subprocess_executor = SubprocessExecutor(max_concurrency=1)

        async def execute_subprocess(label: str) -> ExecutionResult[object]:
            workload = _workload("os.command")
            return await subprocess_executor.execute(
                ResolvedSubprocessWorkload(
                    workload=workload,
                    command=SubprocessCommand(
                        argv=(
                            sys.executable,
                            "-c",
                            "import sys, time; time.sleep(0.08); print(sys.argv[1])",
                            label,
                        )
                    ),
                ),
                _context(workload, label),
            )

        def subprocess_load() -> int:
            return subprocess_executor.current_load

        await _assert_bounded_backpressure(
            execute_subprocess,
            subprocess_load,
            subprocess_executor.close,
        )

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ("process", "subprocess"))
def test_a4_isolated_executor_close_is_idempotent_and_rejects_reuse(
    kind: BackendKind,
) -> None:
    async def scenario() -> None:
        workload = _workload("python.callable" if kind == "process" else "os.command")

        if kind == "process":
            executor = ProcessExecutor(max_workers=1, max_in_flight=1)
            executor.close()
            executor.close()
            with pytest.raises(RuntimeError, match="closed"):
                await executor.execute(
                    ResolvedWorkload(
                        workload=workload,
                        implementation=_process_identity,
                    ),
                    _context(workload, "closed"),
                )
            return

        executor = SubprocessExecutor(max_concurrency=1)
        executor.close()
        executor.close()
        with pytest.raises(RuntimeError, match="closed"):
            await executor.execute(
                ResolvedSubprocessWorkload(
                    workload=workload,
                    command=SubprocessCommand(argv=(sys.executable, "-c", "print('unused')")),
                ),
                _context(workload, "closed"),
            )

    asyncio.run(scenario())


def test_a4_process_conformance_includes_explicit_serialization_failures() -> None:
    async def scenario() -> None:
        executor = ProcessExecutor(max_workers=1, max_in_flight=1)
        workload = _workload("python.callable")

        try:
            result = await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=_process_unpicklable_result,
                ),
                _context(workload, "serialization"),
            )
        finally:
            executor.close()

        assert result.failed
        assert result.failure is not None
        assert result.failure.code.value == "EXECUTOR.PROCESS.RESULT_SERIALIZATION"
        assert result.failure.to_dict()["metadata"]["boundary"] == "pickle"

    asyncio.run(scenario())


def test_a4_subprocess_conformance_preserves_literal_argv_without_shell() -> None:
    async def scenario() -> None:
        workload = _workload("os.command")
        literal = "$(printf should-not-expand)"
        executor = SubprocessExecutor(max_concurrency=1)

        try:
            result = await executor.execute(
                ResolvedSubprocessWorkload(
                    workload=workload,
                    command=SubprocessCommand(
                        argv=(
                            sys.executable,
                            "-c",
                            "import sys; print(sys.argv[1])",
                            literal,
                        )
                    ),
                ),
                _context(workload, "argv"),
            )
        finally:
            executor.close()

        assert result.succeeded
        assert result.stdout == f"{literal}\n"

    asyncio.run(scenario())


def test_a4_isolated_executor_root_api_remains_narrow() -> None:
    assert executors.ProcessExecutorContract is ProcessExecutorContract
    assert executors.SubprocessExecutorContract is SubprocessExecutorContract

    assert not hasattr(executors, "ProcessExecutor")
    assert not hasattr(executors, "SubprocessExecutor")
    assert not hasattr(pyruntimekit, "ProcessExecutor")
    assert not hasattr(pyruntimekit, "SubprocessExecutor")
