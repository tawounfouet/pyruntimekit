"""Tests for the explicit OS subprocess Executor backend."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import (
    AttemptNumber,
    FailureCategory,
    FailureOrigin,
    FailureScope,
    RunId,
    Workload,
    WorkloadDescriptor,
    WorkloadId,
)
from pyruntimekit.executors import (
    SUBPROCESS_EXECUTOR_CAPABILITIES,
    ExecutorCapability,
    ResolvedSubprocessWorkload,
    SubprocessCommand,
    SubprocessExecutorContract,
)
from pyruntimekit.executors.subprocess import SubprocessExecutor

NOW = datetime(2026, 10, 27, 19, 0, tzinfo=UTC)


def _workload() -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="os.command",
            reference="tests.subprocess_executor:command",
        ),
    )


def _context(workload: Workload) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id="subprocess-executor",
    )


def _resolved(
    workload: Workload,
    *argv: str,
    cwd: str | None = None,
    env: tuple[tuple[str, str], ...] = (),
) -> ResolvedSubprocessWorkload:
    return ResolvedSubprocessWorkload(
        workload=workload,
        command=SubprocessCommand(
            argv=argv,
            cwd=cwd,
            env=env,
        ),
    )


def _requires_subprocess_executor(executor: SubprocessExecutorContract) -> None:
    assert executor.descriptor.kind == "subprocess"


def test_subprocess_executor_structurally_satisfies_contract() -> None:
    executor = SubprocessExecutor(clock=lambda: NOW)

    _requires_subprocess_executor(executor)

    assert asyncio.iscoroutinefunction(executor.execute)


def test_subprocess_executor_captures_stdout_stderr_and_zero_exit() -> None:
    async def scenario() -> None:
        workload = _workload()
        result = await SubprocessExecutor(clock=lambda: NOW).execute(
            _resolved(
                workload,
                sys.executable,
                "-c",
                "import sys; print('hello-out'); print('hello-err', file=sys.stderr)",
            ),
            _context(workload),
        )

        assert result.succeeded
        assert result.exit_code == 0
        assert result.stdout == "hello-out\n"
        assert result.stderr == "hello-err\n"
        assert result.failure is None

    asyncio.run(scenario())


def test_subprocess_executor_preserves_argv_without_shell_expansion() -> None:
    async def scenario() -> None:
        workload = _workload()
        literal = "$(printf shell-expanded)"
        result = await SubprocessExecutor(clock=lambda: NOW).execute(
            _resolved(
                workload,
                sys.executable,
                "-c",
                "import sys; print(sys.argv[1])",
                literal,
            ),
            _context(workload),
        )

        assert result.succeeded
        assert result.stdout == f"{literal}\n"

    asyncio.run(scenario())


def test_subprocess_executor_runs_in_separate_process() -> None:
    async def scenario() -> None:
        workload = _workload()
        parent_pid = os.getpid()
        result = await SubprocessExecutor(clock=lambda: NOW).execute(
            _resolved(
                workload,
                sys.executable,
                "-c",
                "import os; print(os.getpid())",
            ),
            _context(workload),
        )

        assert result.succeeded
        assert int(cast(str, result.stdout).strip()) != parent_pid

    asyncio.run(scenario())


def test_subprocess_executor_applies_cwd(tmp_path: Path) -> None:
    async def scenario() -> None:
        workload = _workload()
        result = await SubprocessExecutor(clock=lambda: NOW).execute(
            _resolved(
                workload,
                sys.executable,
                "-c",
                "import os; print(os.getcwd())",
                cwd=str(tmp_path),
            ),
            _context(workload),
        )

        assert result.succeeded
        assert Path(cast(str, result.stdout).strip()) == tmp_path

    asyncio.run(scenario())


def test_subprocess_executor_overlays_environment_without_dropping_parent_env() -> None:
    async def scenario() -> None:
        workload = _workload()
        result = await SubprocessExecutor(clock=lambda: NOW).execute(
            _resolved(
                workload,
                sys.executable,
                "-c",
                (
                    "import os; "
                    "print(os.environ['PYRUNTIMEKIT_TEST_VALUE']); "
                    "print('PATH' in os.environ)"
                ),
                env=(("PYRUNTIMEKIT_TEST_VALUE", "explicit-value"),),
            ),
            _context(workload),
        )

        assert result.succeeded
        assert result.stdout == "explicit-value\nTrue\n"

    asyncio.run(scenario())


def test_subprocess_executor_normalizes_nonzero_exit_and_preserves_streams() -> None:
    async def scenario() -> None:
        workload = _workload()
        result = await SubprocessExecutor(clock=lambda: NOW).execute(
            _resolved(
                workload,
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "print('partial-out'); "
                    "print('bad-command', file=sys.stderr); "
                    "raise SystemExit(7)"
                ),
            ),
            _context(workload),
        )

        assert result.failed
        assert result.exit_code == 7
        assert result.stdout == "partial-out\n"
        assert result.stderr == "bad-command\n"
        assert result.failure is not None

        failure = result.failure
        assert failure.code.value == "EXECUTOR.SUBPROCESS.NONZERO_EXIT"
        assert failure.category is FailureCategory.EXECUTION
        assert failure.origin is FailureOrigin.EXECUTOR
        assert failure.scope is FailureScope.ATTEMPT
        assert failure.occurred_at == NOW
        assert failure.message == "subprocess exited with code 7"
        assert failure.cause is None
        assert failure.traceback_ref is None
        assert failure.to_dict()["metadata"] == {
            "executor": "subprocess.default",
            "workload_kind": "os.command",
            "executable": sys.executable,
        }

    asyncio.run(scenario())


def test_subprocess_executor_normalizes_launch_exception() -> None:
    async def scenario() -> None:
        workload = _workload()
        result = await SubprocessExecutor(clock=lambda: NOW).execute(
            _resolved(
                workload,
                "__pyruntimekit_executable_that_does_not_exist__",
            ),
            _context(workload),
        )

        assert result.failed
        assert result.exit_code is None
        assert result.stdout is None
        assert result.stderr is None
        assert result.failure is not None

        failure = result.failure
        assert failure.code.value == "EXECUTOR.SUBPROCESS.EXCEPTION"
        assert failure.category is FailureCategory.EXECUTION
        assert failure.origin is FailureOrigin.EXECUTOR
        assert failure.scope is FailureScope.ATTEMPT
        assert failure.occurred_at == NOW
        assert failure.cause is not None
        assert failure.cause.type_name == "FileNotFoundError"
        assert failure.traceback_ref is None
        assert failure.to_dict()["metadata"] == {
            "executor": "subprocess.default",
            "workload_kind": "os.command",
            "executable": "__pyruntimekit_executable_that_does_not_exist__",
        }

    asyncio.run(scenario())


def test_subprocess_executor_capabilities_are_truthful_for_pr33() -> None:
    descriptor = SubprocessExecutor(clock=lambda: NOW).descriptor

    assert descriptor.name == "subprocess.default"
    assert descriptor.kind == "subprocess"
    assert descriptor.capabilities == SUBPROCESS_EXECUTOR_CAPABILITIES
    assert descriptor.capabilities.values == frozenset(
        {
            ExecutorCapability.TRUSTED_ONLY,
            ExecutorCapability.SUBPROCESS_EXECUTION,
            ExecutorCapability.PROCESS_ISOLATION,
            ExecutorCapability.BOUNDED_CAPACITY,
        }
    )
    assert not descriptor.capabilities.supports(ExecutorCapability.IN_PROCESS)
    assert not descriptor.capabilities.supports(ExecutorCapability.SHARED_MEMORY)
    assert not descriptor.capabilities.supports(ExecutorCapability.SERIALIZED_BOUNDARY)
    assert descriptor.capabilities.supports(ExecutorCapability.BOUNDED_CAPACITY)


def test_subprocess_executor_validates_contract_inputs() -> None:
    async def scenario() -> None:
        workload = _workload()
        context = _context(workload)
        executor = SubprocessExecutor(clock=lambda: NOW)

        with pytest.raises(TypeError, match="ResolvedSubprocessWorkload"):
            await executor.execute(cast(Any, object()), context)

        resolved = _resolved(workload, sys.executable, "--version")
        with pytest.raises(TypeError, match="ExecutionContext"):
            await executor.execute(resolved, cast(Any, object()))

    asyncio.run(scenario())

    with pytest.raises(TypeError, match="max_concurrency"):
        SubprocessExecutor(max_concurrency=cast(Any, True), clock=lambda: NOW)

    with pytest.raises(TypeError, match="max_concurrency"):
        SubprocessExecutor(max_concurrency=cast(Any, "2"), clock=lambda: NOW)

    with pytest.raises(ValueError, match=">= 1"):
        SubprocessExecutor(max_concurrency=0, clock=lambda: NOW)

    with pytest.raises(TypeError, match="clock must be callable"):
        SubprocessExecutor(clock=cast(Any, object()))


def test_subprocess_executor_rejects_context_for_other_workload() -> None:
    async def scenario() -> None:
        workload = _workload()
        other = _workload()

        with pytest.raises(ValueError, match="share workload_id"):
            await SubprocessExecutor(clock=lambda: NOW).execute(
                _resolved(workload, sys.executable, "--version"),
                _context(other),
            )

    asyncio.run(scenario())


def test_subprocess_executor_bounds_active_commands() -> None:
    async def scenario() -> None:
        executor = SubprocessExecutor(
            max_concurrency=1,
            clock=lambda: NOW,
        )

        async def submit_one(label: str) -> object:
            workload = _workload()
            return await executor.execute(
                _resolved(
                    workload,
                    sys.executable,
                    "-c",
                    "import sys, time; time.sleep(0.08); print(sys.argv[1])",
                    label,
                ),
                _context(workload),
            )

        first = asyncio.create_task(submit_one("first"))
        second = asyncio.create_task(submit_one("second"))

        for _ in range(300):
            if executor.current_load == 1:
                break
            await asyncio.sleep(0.001)

        assert executor.max_concurrency == 1
        assert executor.current_load == 1
        assert not second.done()

        first_result, second_result = await asyncio.gather(first, second)
        await asyncio.sleep(0)

        assert first_result.stdout == "first\n"
        assert second_result.stdout == "second\n"
        assert executor.current_load == 0

    asyncio.run(scenario())


def test_subprocess_cancellation_cleanup_releases_capacity(tmp_path: Path) -> None:
    async def scenario() -> None:
        executor = SubprocessExecutor(
            max_concurrency=1,
            clock=lambda: NOW,
        )
        signal_path = tmp_path / "subprocess-started"
        workload = _workload()
        task = asyncio.create_task(
            executor.execute(
                _resolved(
                    workload,
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; import sys, time; "
                        "Path(sys.argv[1]).write_text('started'); "
                        "time.sleep(2)"
                    ),
                    str(signal_path),
                ),
                _context(workload),
            )
        )

        for _ in range(500):
            if signal_path.exists():
                break
            await asyncio.sleep(0.001)

        assert signal_path.exists()
        assert executor.current_load == 1

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert executor.current_load == 0

        next_workload = _workload()
        result = await executor.execute(
            _resolved(
                next_workload,
                sys.executable,
                "-c",
                "print('after-cancel')",
            ),
            _context(next_workload),
        )

        assert result.succeeded
        assert result.stdout == "after-cancel\n"
        assert executor.current_load == 0

    asyncio.run(scenario())


def test_subprocess_close_is_idempotent_and_prevents_new_execution() -> None:
    async def scenario() -> None:
        executor = SubprocessExecutor(clock=lambda: NOW)
        workload = _workload()

        executor.close()
        executor.close()

        with pytest.raises(RuntimeError, match="SubprocessExecutor is closed"):
            await executor.execute(
                _resolved(workload, sys.executable, "--version"),
                _context(workload),
            )

    asyncio.run(scenario())
