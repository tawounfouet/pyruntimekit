"""OS subprocess Executor backend."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime

from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain.enums import (
    FailureCategory,
    FailureOrigin,
    FailureScope,
    FailureSeverity,
)
from pyruntimekit.domain.failure import Failure, FailureCauseSummary, FailureCode
from pyruntimekit.domain.result import ExecutionResult

from .base import ExecutorDescriptor, ResolvedSubprocessWorkload
from .capabilities import SUBPROCESS_EXECUTOR_CAPABILITIES

type SubprocessExecutorClock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _decode_output(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


class SubprocessExecutor:
    """Execute explicit OS commands with bounded local concurrency."""

    __slots__ = (
        "_capacity",
        "_clock",
        "_closed",
        "_current_load",
        "_max_concurrency",
    )

    _DESCRIPTOR = ExecutorDescriptor(
        name="subprocess.default",
        kind="subprocess",
        capabilities=SUBPROCESS_EXECUTOR_CAPABILITIES,
    )

    def __init__(
        self,
        *,
        max_concurrency: int = 32,
        clock: SubprocessExecutorClock = _utc_now,
    ) -> None:
        if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int):
            raise TypeError("max_concurrency must be an int")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self._clock = clock
        self._closed = False
        self._max_concurrency = max_concurrency
        self._current_load = 0
        self._capacity = asyncio.BoundedSemaphore(max_concurrency)

    @property
    def descriptor(self) -> ExecutorDescriptor:
        """Describe the guarantees currently implemented by SubprocessExecutor."""
        return self._DESCRIPTOR

    @property
    def max_concurrency(self) -> int:
        """Return the maximum number of active subprocess executions."""
        return self._max_concurrency

    @property
    def current_load(self) -> int:
        """Return the number of subprocess executions currently holding capacity."""
        return self._current_load

    async def execute(
        self,
        workload: ResolvedSubprocessWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]:
        """Execute one explicit command only after bounded capacity is available."""
        if not isinstance(workload, ResolvedSubprocessWorkload):
            raise TypeError("workload must be a ResolvedSubprocessWorkload")
        if not isinstance(context, ExecutionContext):
            raise TypeError("context must be an ExecutionContext")
        if workload.workload_id != context.workload_id:
            raise ValueError(
                "ResolvedSubprocessWorkload and ExecutionContext must share workload_id"
            )
        if self._closed:
            raise RuntimeError("SubprocessExecutor is closed")

        await self._capacity.acquire()
        if self._closed:
            self._capacity.release()
            raise RuntimeError("SubprocessExecutor is closed")

        self._current_load += 1

        try:
            return await self._execute_with_capacity(workload)
        finally:
            self._current_load -= 1
            self._capacity.release()

    async def _execute_with_capacity(
        self,
        workload: ResolvedSubprocessWorkload,
    ) -> ExecutionResult[object]:
        command = workload.command
        environment = os.environ.copy()
        environment.update(dict(command.env))
        process: asyncio.subprocess.Process | None = None

        try:
            process = await asyncio.create_subprocess_exec(
                *command.argv,
                cwd=command.cwd,
                env=environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await process.communicate()
        except asyncio.CancelledError:
            if process is not None and process.returncode is None:
                process.terminate()
                await asyncio.shield(process.wait())
            raise
        except Exception as exc:
            return self._exception_result(exc, workload)

        stdout = _decode_output(stdout_bytes)
        stderr = _decode_output(stderr_bytes)
        exit_code = process.returncode
        assert exit_code is not None

        if exit_code == 0:
            return ExecutionResult[object].success(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
            )

        failure = Failure.create(
            code=FailureCode("EXECUTOR.SUBPROCESS.NONZERO_EXIT"),
            category=FailureCategory.EXECUTION,
            origin=FailureOrigin.EXECUTOR,
            severity=FailureSeverity.ERROR,
            scope=FailureScope.ATTEMPT,
            message=f"subprocess exited with code {exit_code}",
            retryable=False,
            recoverable=False,
            occurred_at=self._clock(),
            metadata={
                "executor": self._DESCRIPTOR.name,
                "workload_kind": workload.workload.kind,
                "executable": command.argv[0],
            },
        )
        return ExecutionResult[object].from_failure(
            failure,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    def _exception_result(
        self,
        exc: Exception,
        workload: ResolvedSubprocessWorkload,
    ) -> ExecutionResult[object]:
        failure = Failure.create(
            code=FailureCode("EXECUTOR.SUBPROCESS.EXCEPTION"),
            category=FailureCategory.EXECUTION,
            origin=FailureOrigin.EXECUTOR,
            severity=FailureSeverity.ERROR,
            scope=FailureScope.ATTEMPT,
            message=str(exc) or type(exc).__name__,
            retryable=False,
            recoverable=False,
            cause=FailureCauseSummary(
                type_name=type(exc).__name__,
                message=str(exc) or None,
            ),
            occurred_at=self._clock(),
            metadata={
                "executor": self._DESCRIPTOR.name,
                "workload_kind": workload.workload.kind,
                "executable": workload.command.argv[0],
            },
        )
        return ExecutionResult[object].from_failure(failure)

    def close(self) -> None:
        """Reject new subprocess executions without terminating active commands."""
        if self._closed:
            return
        self._closed = True


__all__ = ["SubprocessExecutor", "SubprocessExecutorClock"]
