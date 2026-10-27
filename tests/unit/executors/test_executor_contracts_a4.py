"""Contract evolution tests for the 0.1.0a4 executor milestone."""

from __future__ import annotations

import importlib.util
import inspect
from datetime import UTC, datetime
from typing import Any, cast

import pytest

import pyruntimekit
import pyruntimekit.executors as executors

from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import (
    AttemptNumber,
    ExecutionResult,
    RunId,
    Workload,
    WorkloadDescriptor,
    WorkloadId,
)
from pyruntimekit.executors import (
    ASYNC_EXECUTOR_CAPABILITIES,
    INLINE_EXECUTOR_CAPABILITIES,
    THREAD_EXECUTOR_CAPABILITIES,
    ExecutorCapabilities,
    ExecutorCapability,
    ExecutorDescriptor,
    ProcessExecutorContract,
    ResolvedSubprocessWorkload,
    ResolvedWorkload,
    SubprocessCommand,
    SubprocessExecutorContract,
)

NOW = datetime(2026, 10, 27, 18, 0, tzinfo=UTC)


def _workload(kind: str = "python.callable") -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind=kind,
            reference="tests.executor_contracts_a4:work",
        ),
    )


def _context(workload: Workload) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id="a4-contracts",
    )


def _requires_process_executor(executor: ProcessExecutorContract) -> None:
    assert executor.descriptor.kind


def _requires_subprocess_executor(executor: SubprocessExecutorContract) -> None:
    assert executor.descriptor.kind


class FakeProcessExecutor:
    _DESCRIPTOR = ExecutorDescriptor(
        name="test.process",
        kind="process",
        capabilities=ExecutorCapabilities(
            frozenset(
                {
                    ExecutorCapability.PROCESS_EXECUTION,
                    ExecutorCapability.PROCESS_ISOLATION,
                    ExecutorCapability.SERIALIZED_BOUNDARY,
                }
            )
        ),
    )

    @property
    def descriptor(self) -> ExecutorDescriptor:
        return self._DESCRIPTOR

    async def execute(
        self,
        workload: ResolvedWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]:
        return ExecutionResult[object].success(
            value=(workload.workload_id, context.workload_id)
        )


class FakeSubprocessExecutor:
    _DESCRIPTOR = ExecutorDescriptor(
        name="test.subprocess",
        kind="subprocess",
        capabilities=ExecutorCapabilities(
            frozenset(
                {
                    ExecutorCapability.SUBPROCESS_EXECUTION,
                    ExecutorCapability.PROCESS_ISOLATION,
                }
            )
        ),
    )

    @property
    def descriptor(self) -> ExecutorDescriptor:
        return self._DESCRIPTOR

    async def execute(
        self,
        workload: ResolvedSubprocessWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]:
        return ExecutionResult[object].success(
            value=(workload.command.argv, context.workload_id)
        )


def test_process_executor_contract_is_awaitable_and_structural() -> None:
    executor = FakeProcessExecutor()

    _requires_process_executor(executor)

    assert inspect.iscoroutinefunction(executor.execute)


def test_subprocess_executor_contract_is_awaitable_and_structural() -> None:
    executor = FakeSubprocessExecutor()

    _requires_subprocess_executor(executor)

    assert inspect.iscoroutinefunction(executor.execute)


def test_subprocess_command_preserves_explicit_immutable_boundary() -> None:
    command = SubprocessCommand(
        argv=("python", "-c", "print('ok')"),
        cwd=" /tmp ",
        env=(("PYTHONUTF8", "1"),),
    )

    assert command.argv == ("python", "-c", "print('ok')")
    assert command.cwd == "/tmp"
    assert command.env == (("PYTHONUTF8", "1"),)


@pytest.mark.parametrize(
    ("argv", "error", "message"),
    [
        (cast(Any, ["python"]), TypeError, "argv must be a tuple of strings"),
        ((), ValueError, "argv must contain at least one argument"),
        (("",), ValueError, "argv\[0\] must be a non-empty executable"),
        (cast(Any, ("python", 1)), TypeError, "argv must contain only strings"),
    ],
)
def test_subprocess_command_rejects_invalid_argv(
    argv: tuple[str, ...],
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        SubprocessCommand(argv=argv)


def test_subprocess_command_validates_cwd_and_environment() -> None:
    with pytest.raises(ValueError, match="cwd must not be empty"):
        SubprocessCommand(argv=("python",), cwd="   ")

    with pytest.raises(TypeError, match="env must be a tuple"):
        SubprocessCommand(argv=("python",), env=cast(Any, {"A": "1"}))

    with pytest.raises(TypeError, match="env must contain only"):
        SubprocessCommand(argv=("python",), env=cast(Any, (("A", "1", "x"),)))

    with pytest.raises(ValueError, match="env key must not be empty"):
        SubprocessCommand(argv=("python",), env=((" ", "1"),))

    with pytest.raises(TypeError, match="env values must be strings"):
        SubprocessCommand(argv=("python",), env=cast(Any, (("A", 1),)))


def test_resolved_subprocess_workload_preserves_domain_identity() -> None:
    workload = _workload("os.command")
    command = SubprocessCommand(argv=("python", "--version"))

    resolved = ResolvedSubprocessWorkload(workload=workload, command=command)

    assert resolved.workload is workload
    assert resolved.command is command
    assert resolved.workload_id == workload.workload_id


def test_resolved_subprocess_workload_validates_runtime_shape() -> None:
    workload = _workload("os.command")
    command = SubprocessCommand(argv=("python", "--version"))

    with pytest.raises(TypeError, match="workload must be a Workload"):
        ResolvedSubprocessWorkload(
            workload=cast(Any, object()),
            command=command,
        )

    with pytest.raises(TypeError, match="command must be a SubprocessCommand"):
        ResolvedSubprocessWorkload(
            workload=workload,
            command=cast(Any, object()),
        )


def test_a4_capability_vocabulary_is_stable() -> None:
    assert {capability.value for capability in ExecutorCapability} == {
        "IN_PROCESS",
        "SHARED_MEMORY",
        "TRUSTED_ONLY",
        "ASYNC_EXECUTION",
        "THREAD_EXECUTION",
        "PROCESS_EXECUTION",
        "SUBPROCESS_EXECUTION",
        "PROCESS_ISOLATION",
        "SERIALIZED_BOUNDARY",
        "CONTEXTVARS_PROPAGATION",
        "THREAD_CONTEXT_PROPAGATION",
        "BOUNDED_CAPACITY",
    }


def test_existing_executor_capability_sets_remain_unchanged() -> None:
    assert INLINE_EXECUTOR_CAPABILITIES.values == frozenset(
        {
            ExecutorCapability.IN_PROCESS,
            ExecutorCapability.SHARED_MEMORY,
            ExecutorCapability.TRUSTED_ONLY,
        }
    )
    assert ASYNC_EXECUTOR_CAPABILITIES.values == frozenset(
        {
            ExecutorCapability.IN_PROCESS,
            ExecutorCapability.SHARED_MEMORY,
            ExecutorCapability.TRUSTED_ONLY,
            ExecutorCapability.ASYNC_EXECUTION,
            ExecutorCapability.CONTEXTVARS_PROPAGATION,
            ExecutorCapability.BOUNDED_CAPACITY,
        }
    )
    assert THREAD_EXECUTOR_CAPABILITIES.values == frozenset(
        {
            ExecutorCapability.IN_PROCESS,
            ExecutorCapability.SHARED_MEMORY,
            ExecutorCapability.TRUSTED_ONLY,
            ExecutorCapability.THREAD_EXECUTION,
            ExecutorCapability.THREAD_CONTEXT_PROPAGATION,
            ExecutorCapability.BOUNDED_CAPACITY,
        }
    )


def test_process_and_subprocess_capabilities_are_not_granted_implicitly() -> None:
    for capabilities in (
        INLINE_EXECUTOR_CAPABILITIES,
        ASYNC_EXECUTOR_CAPABILITIES,
        THREAD_EXECUTOR_CAPABILITIES,
    ):
        assert not capabilities.supports(ExecutorCapability.PROCESS_EXECUTION)
        assert not capabilities.supports(ExecutorCapability.SUBPROCESS_EXECUTION)
        assert not capabilities.supports(ExecutorCapability.PROCESS_ISOLATION)
        assert not capabilities.supports(ExecutorCapability.SERIALIZED_BOUNDARY)


def test_a4_contracts_do_not_expand_root_api_or_add_backends_yet() -> None:
    assert executors.ProcessExecutorContract is ProcessExecutorContract
    assert executors.SubprocessExecutorContract is SubprocessExecutorContract
    assert executors.ResolvedSubprocessWorkload is ResolvedSubprocessWorkload
    assert executors.SubprocessCommand is SubprocessCommand

    assert not hasattr(pyruntimekit, "ProcessExecutor")
    assert not hasattr(pyruntimekit, "SubprocessExecutor")
    assert not hasattr(pyruntimekit, "ProcessExecutorContract")
    assert not hasattr(pyruntimekit, "SubprocessExecutorContract")

    assert importlib.util.find_spec("pyruntimekit.executors.process") is None
    assert importlib.util.find_spec("pyruntimekit.executors.subprocess") is None
