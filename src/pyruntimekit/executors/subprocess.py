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
    """Execute explicit OS commands without an implicit shell."""

    __slots__ = ("_clock",)

    _DESCRIPTOR = ExecutorDescriptor(
        name="subprocess.default",
        kind="subprocess",
        capabilities=SUBPROCESS_EXECUTOR_CAPABILITIES,
    )

    def __init__(
        self,
        *,
        clock: SubprocessExecutorClock = _utc_now,
    ) -> None:
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._clock = clock

    @property
    def descriptor(self) -> ExecutorDescriptor:
        """Describe the guarantees currently implemented by SubprocessExecutor."""
        return self._DESCRIPTOR

    async def execute(
        self,
        workload: ResolvedSubprocessWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]:
        """Execute one explicit command and normalize its exit semantics."""
        if not isinstance(workload, ResolvedSubprocessWorkload):
            raise TypeError("workload must be a ResolvedSubprocessWorkload")
        if not isinstance(context, ExecutionContext):
            raise TypeError("context must be an ExecutionContext")
        if workload.workload_id != context.workload_id:
            raise ValueError(
                "ResolvedSubprocessWorkload and ExecutionContext must share workload_id"
            )

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


__all__ = ["SubprocessExecutor", "SubprocessExecutorClock"]
