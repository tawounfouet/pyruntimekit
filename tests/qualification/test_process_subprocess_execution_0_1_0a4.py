"""Milestone execution qualification for PyRuntimeKit 0.1.0a4."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import cast

import pytest

from pyruntimekit import RunHandle, Runtime
from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain import (
    AttemptNumber,
    ExecutionResult,
    FailureCategory,
    FailureOrigin,
    FailureScope,
    RunId,
    RunState,
    Workload,
    WorkloadDescriptor,
    WorkloadId,
)
from pyruntimekit.executors import (
    ResolvedSubprocessWorkload,
    ResolvedWorkload,
    SubprocessCommand,
)
from pyruntimekit.executors.process import ProcessExecutor
from pyruntimekit.executors.subprocess import SubprocessExecutor


def _workload(kind: str) -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind=kind,
            reference="tests.qualification.a4:work",
        ),
    )


def _context(workload: Workload, label: str = "a4-qualification") -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id=label,
    )


def _process_observe(context: ExecutionContext) -> object:
    return (
        os.getpid(),
        context.correlation_id,
        context.workload_id.value,
        context.attempt.value,
    )


def _process_existing_result(context: ExecutionContext) -> object:
    return ExecutionResult[object].success(
        value={"correlation": context.correlation_id},
        metadata={"producer": "isolated-child"},
    )


def _process_raise(context: ExecutionContext) -> object:
    raise ValueError(f"qualification-exception:{context.correlation_id}")


def _process_unserializable_result(context: ExecutionContext) -> object:
    return lambda: context.correlation_id


def _process_signal_and_sleep(context: ExecutionContext) -> object:
    Path(context.correlation_id).write_text("started", encoding="utf-8")
    time.sleep(0.3)
    return "finished"


async def _await_file(path: Path) -> None:
    async def wait_for_file() -> None:
        while not path.exists():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(wait_for_file(), timeout=5)


def _process_resolved(
    workload: Workload,
    implementation: object,
) -> ResolvedWorkload:
    from typing import Any

    return ResolvedWorkload(workload=workload, implementation=cast(Any, implementation))


def _command_resolved(
    workload: Workload,
    code: str,
    *args: str,
    cwd: str | None = None,
    env: tuple[tuple[str, str], ...] = (),
) -> ResolvedSubprocessWorkload:
    return ResolvedSubprocessWorkload(
        workload=workload,
        command=SubprocessCommand(
            argv=(sys.executable, "-c", code, *args),
            cwd=cwd,
            env=env,
        ),
    )


def test_a4_retains_a2_synchronous_public_runtime_and_handle() -> None:
    runtime = Runtime()
    handle = runtime.submit(
        lambda context: (os.getpid(), context.correlation_id),
        correlation_id="a4-public-compatibility",
    )

    assert isinstance(handle, RunHandle)
    assert handle.status() is RunState.SUCCEEDED
    assert handle.result().succeeded
    assert handle.result().value == (os.getpid(), "a4-public-compatibility")
    assert handle.wait() is handle.result()


def test_a4_process_preserves_exact_context_in_real_child() -> None:
    async def scenario() -> None:
        workload = _workload("python.callable")
        context = _context(workload, "a4-child")
        executor = ProcessExecutor(max_workers=1, max_in_flight=1)

        try:
            result = await executor.execute(
                _process_resolved(workload, _process_observe),
                context,
            )
        finally:
            executor.close()

        assert result.succeeded
        child_pid, label, workload_id, attempt = cast(tuple[int, str, str, int], result.value)
        assert child_pid != os.getpid()
        assert label == "a4-child"
        assert workload_id == workload.workload_id.value
        assert attempt == 1
        assert executor.current_load == 0

    asyncio.run(scenario())


def test_a4_process_existing_execution_result_survives_pickle_round_trip() -> None:
    async def scenario() -> None:
        workload = _workload("python.callable")
        executor = ProcessExecutor(max_workers=1, max_in_flight=1)

        try:
            result = await executor.execute(
                _process_resolved(workload, _process_existing_result),
                _context(workload, "serialized-result"),
            )
        finally:
            executor.close()

        assert result.succeeded
        assert result.value == {"correlation": "serialized-result"}
        assert result.metadata_dict() == {"producer": "isolated-child"}

    asyncio.run(scenario())


def test_a4_process_qualifies_distinct_workload_and_transport_failures() -> None:
    async def scenario() -> None:
        executor = ProcessExecutor(max_workers=1, max_in_flight=1)
        try:
            workload = _workload("python.callable")
            ordinary = await executor.execute(
                _process_resolved(workload, _process_raise),
                _context(workload, "ordinary"),
            )
            unserializable = await executor.execute(
                _process_resolved(workload, _process_unserializable_result),
                _context(workload, "result"),
            )
            input_failure = await executor.execute(
                _process_resolved(workload, lambda context: context.correlation_id),
                _context(workload, "input"),
            )
        finally:
            executor.close()

        for result, code in (
            (ordinary, "EXECUTOR.PROCESS.EXCEPTION"),
            (unserializable, "EXECUTOR.PROCESS.RESULT_SERIALIZATION"),
            (input_failure, "EXECUTOR.PROCESS.INPUT_SERIALIZATION"),
        ):
            assert result.failed
            assert result.failure is not None
            assert result.failure.code.value == code
            assert result.failure.category is FailureCategory.EXECUTION
            assert result.failure.origin is FailureOrigin.EXECUTOR
            assert result.failure.scope is FailureScope.ATTEMPT
            assert result.failure.traceback_ref is None

        assert executor.current_load == 0

    asyncio.run(scenario())


def test_a4_subprocess_preserves_native_boundary_and_environment(tmp_path: Path) -> None:
    async def scenario() -> None:
        workload = _workload("os.command")
        literal = "$(echo never-expand)"
        code = (
            "import json, os, sys; "
            "print(json.dumps([os.getpid(), os.getcwd(), "
            "os.environ['PYRUNTIMEKIT_A4_MARKER'], sys.argv[1]])); "
            "print('diagnostic', file=sys.stderr)"
        )
        executor = SubprocessExecutor(max_concurrency=1)
        try:
            result = await executor.execute(
                _command_resolved(
                    workload,
                    code,
                    literal,
                    cwd=str(tmp_path),
                    env=(("PYRUNTIMEKIT_A4_MARKER", "explicit"),),
                ),
                _context(workload),
            )
        finally:
            executor.close()

        assert result.succeeded
        assert result.exit_code == 0
        assert result.stdout is not None
        child_pid, directory, marker, argument = json.loads(result.stdout)
        assert child_pid != os.getpid()
        assert Path(directory) == tmp_path
        assert marker == "explicit"
        assert argument == literal
        assert result.stderr == "diagnostic\n"
        assert executor.current_load == 0

    asyncio.run(scenario())


def test_a4_subprocess_nonzero_exit_and_launch_errors_remain_distinct() -> None:
    async def scenario() -> None:
        executor = SubprocessExecutor(max_concurrency=1)
        workload = _workload("os.command")
        try:
            nonzero = await executor.execute(
                _command_resolved(
                    workload,
                    "import sys; print('partial'); print('bad', file=sys.stderr); "
                    "raise SystemExit(19)",
                ),
                _context(workload),
            )
            missing = await executor.execute(
                ResolvedSubprocessWorkload(
                    workload=workload,
                    command=SubprocessCommand(argv=("__missing_pyruntimekit_a4_executable__",)),
                ),
                _context(workload),
            )
        finally:
            executor.close()

        assert nonzero.failed
        assert nonzero.exit_code == 19
        assert nonzero.stdout == "partial\n"
        assert nonzero.stderr == "bad\n"
        assert nonzero.failure is not None
        assert nonzero.failure.code.value == "EXECUTOR.SUBPROCESS.NONZERO_EXIT"

        assert missing.failed
        assert missing.failure is not None
        assert missing.failure.code.value == "EXECUTOR.SUBPROCESS.EXCEPTION"
        assert missing.exit_code is None
        assert missing.failure.cause is not None
        assert missing.failure.cause.type_name == "FileNotFoundError"
        assert executor.current_load == 0

    asyncio.run(scenario())


def test_a4_process_cancelled_await_retains_capacity_until_child_finishes(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        started = tmp_path / "process-started"
        executor = ProcessExecutor(max_workers=1, max_in_flight=1)
        workload = _workload("python.callable")
        active = asyncio.create_task(
            executor.execute(
                _process_resolved(workload, _process_signal_and_sleep),
                _context(workload, str(started)),
            )
        )
        try:
            await _await_file(started)
            assert executor.current_load == 1
            active.cancel()
            with pytest.raises(asyncio.CancelledError):
                await active
            assert executor.current_load == 1

            replacement = _workload("python.callable")
            queued = asyncio.create_task(
                executor.execute(
                    _process_resolved(replacement, _process_observe),
                    _context(replacement, "replacement"),
                )
            )
            await asyncio.sleep(0)
            assert not queued.done()
            assert executor.current_load == 1

            result = await asyncio.wait_for(queued, timeout=5)
            assert result.succeeded
            await asyncio.sleep(0)
            assert executor.current_load == 0
        finally:
            executor.close()

    asyncio.run(scenario())


def test_a4_subprocess_cancellation_waits_for_cleanup_before_releasing_slot(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        started = tmp_path / "subprocess-started"
        executor = SubprocessExecutor(max_concurrency=1)
        workload = _workload("os.command")
        task = asyncio.create_task(
            executor.execute(
                _command_resolved(
                    workload,
                    "from pathlib import Path; import sys, time; "
                    "Path(sys.argv[1]).write_text('started'); time.sleep(3)",
                    str(started),
                ),
                _context(workload),
            )
        )

        await _await_file(started)
        assert executor.current_load == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert executor.current_load == 0

        replacement = _workload("os.command")
        result = await executor.execute(
            _command_resolved(replacement, "print('replacement')"),
            _context(replacement),
        )
        executor.close()
        assert result.succeeded
        assert result.stdout == "replacement\n"
        assert executor.current_load == 0

    asyncio.run(scenario())


def test_a4_subprocess_close_does_not_terminate_active_command(tmp_path: Path) -> None:
    async def scenario() -> None:
        started = tmp_path / "close-started"
        workload = _workload("os.command")
        executor = SubprocessExecutor(max_concurrency=1)
        task = asyncio.create_task(
            executor.execute(
                _command_resolved(
                    workload,
                    "from pathlib import Path; import sys, time; "
                    "Path(sys.argv[1]).write_text('started'); "
                    "time.sleep(0.12); print('completed')",
                    str(started),
                ),
                _context(workload),
            )
        )

        await _await_file(started)
        executor.close()
        executor.close()
        result = await asyncio.wait_for(task, timeout=5)
        assert result.succeeded
        assert result.stdout == "completed\n"
        assert executor.current_load == 0

        with pytest.raises(RuntimeError, match="closed"):
            await executor.execute(
                _command_resolved(workload, "print('not-run')"),
                _context(workload),
            )

    asyncio.run(scenario())
