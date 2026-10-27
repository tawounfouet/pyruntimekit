"""Child-process Executor backend."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
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

from .base import ExecutorDescriptor, ResolvedWorkload
from .capabilities import PROCESS_EXECUTOR_CAPABILITIES
from .process_serialization import (
    ProcessResultSerializationError,
    deserialize_process_result,
    preflight_process_submission,
    serialize_process_result,
)

type ProcessExecutorClock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _invoke_workload(
    workload: ResolvedWorkload,
    context: ExecutionContext,
) -> bytes:
    outcome = workload.implementation(context)
    return serialize_process_result(outcome)


class ProcessExecutor:
    """Execute synchronous Workloads in an owned child-process pool."""

    __slots__ = ("_clock", "_closed", "_pool")

    _DESCRIPTOR = ExecutorDescriptor(
        name="process.default",
        kind="process",
        capabilities=PROCESS_EXECUTOR_CAPABILITIES,
    )

    def __init__(
        self,
        *,
        max_workers: int | None = None,
        clock: ProcessExecutorClock = _utc_now,
    ) -> None:
        if max_workers is not None:
            if isinstance(max_workers, bool) or not isinstance(max_workers, int):
                raise TypeError("max_workers must be an int or None")
            if max_workers < 1:
                raise ValueError("max_workers must be >= 1")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self._clock = clock
        self._closed = False
        self._pool = ProcessPoolExecutor(max_workers=max_workers)

    @property
    def descriptor(self) -> ExecutorDescriptor:
        """Describe the guarantees currently implemented by ProcessExecutor."""
        return self._DESCRIPTOR

    async def execute(
        self,
        workload: ResolvedWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]:
        """Submit one synchronous Workload to a child process."""
        if not isinstance(workload, ResolvedWorkload):
            raise TypeError("workload must be a ResolvedWorkload")
        if not isinstance(context, ExecutionContext):
            raise TypeError("context must be an ExecutionContext")
        if workload.workload_id != context.workload_id:
            raise ValueError("ResolvedWorkload and ExecutionContext must share workload_id")
        if self._closed:
            raise RuntimeError("ProcessExecutor is closed")

        try:
            preflight_process_submission(workload, context)
        except Exception as exc:
            return self._serialization_failure_result(
                code="EXECUTOR.PROCESS.INPUT_SERIALIZATION",
                message="process submission is not serializable",
                type_name=type(exc).__name__,
                cause_message=str(exc) or None,
                workload=workload,
            )

        loop = asyncio.get_running_loop()

        try:
            concurrent_future = self._pool.submit(
                _invoke_workload,
                workload,
                context,
            )
            payload = await asyncio.wrap_future(concurrent_future, loop=loop)
        except ProcessResultSerializationError as exc:
            return self._serialization_failure_result(
                code="EXECUTOR.PROCESS.RESULT_SERIALIZATION",
                message="process result is not serializable",
                type_name=exc.type_name,
                cause_message=exc.cause_message,
                workload=workload,
            )
        except Exception as exc:
            return self._failure_result(exc, workload)

        try:
            outcome = deserialize_process_result(payload)
        except Exception as exc:
            return self._serialization_failure_result(
                code="EXECUTOR.PROCESS.RESULT_DESERIALIZATION",
                message="process result could not be deserialized",
                type_name=type(exc).__name__,
                cause_message=str(exc) or None,
                workload=workload,
            )

        if isinstance(outcome, ExecutionResult):
            return outcome
        return ExecutionResult[object].success(value=outcome)

    def _serialization_failure_result(
        self,
        *,
        code: str,
        message: str,
        type_name: str,
        cause_message: str | None,
        workload: ResolvedWorkload,
    ) -> ExecutionResult[object]:
        failure = Failure.create(
            code=FailureCode(code),
            category=FailureCategory.EXECUTION,
            origin=FailureOrigin.EXECUTOR,
            severity=FailureSeverity.ERROR,
            scope=FailureScope.ATTEMPT,
            message=message,
            retryable=False,
            recoverable=False,
            cause=FailureCauseSummary(
                type_name=type_name,
                message=cause_message,
            ),
            occurred_at=self._clock(),
            metadata={
                "executor": self._DESCRIPTOR.name,
                "workload_kind": workload.workload.kind,
                "boundary": "pickle",
            },
        )
        return ExecutionResult[object].from_failure(failure)

    def _failure_result(
        self,
        exc: Exception,
        workload: ResolvedWorkload,
    ) -> ExecutionResult[object]:
        failure = Failure.create(
            code=FailureCode("EXECUTOR.PROCESS.EXCEPTION"),
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
            },
        )
        return ExecutionResult[object].from_failure(failure)

    def close(
        self,
        *,
        wait: bool = True,
        cancel_futures: bool = False,
    ) -> None:
        """Shut down the owned process pool once."""
        if self._closed:
            return
        self._closed = True
        self._pool.shutdown(
            wait=wait,
            cancel_futures=cancel_futures,
        )


__all__ = ["ProcessExecutor", "ProcessExecutorClock"]
