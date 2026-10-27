"""Asynchronous in-process Executor backend."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
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

from .base import ExecutorDescriptor, ResolvedAsyncWorkload
from .capabilities import ASYNC_EXECUTOR_CAPABILITIES

type AsyncExecutorClock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def _await_outcome(awaitable: Awaitable[object]) -> object:
    return await awaitable


class AsyncExecutor:
    """Execute one resolved async callable in an explicit asyncio Task."""

    __slots__ = ("_clock",)

    _DESCRIPTOR = ExecutorDescriptor(
        name="async.default",
        kind="async",
        capabilities=ASYNC_EXECUTOR_CAPABILITIES,
    )

    def __init__(self, *, clock: AsyncExecutorClock = _utc_now) -> None:
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._clock = clock

    @property
    def descriptor(self) -> ExecutorDescriptor:
        """Describe the guarantees currently implemented by AsyncExecutor."""
        return self._DESCRIPTOR

    async def execute(
        self,
        workload: ResolvedAsyncWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]:
        """Execute once in an asyncio Task and normalize ordinary exceptions."""
        if not isinstance(workload, ResolvedAsyncWorkload):
            raise TypeError("workload must be a ResolvedAsyncWorkload")
        if not isinstance(context, ExecutionContext):
            raise TypeError("context must be an ExecutionContext")
        if workload.workload_id != context.workload_id:
            raise ValueError("ResolvedAsyncWorkload and ExecutionContext must share workload_id")

        try:
            awaitable = workload.implementation(context)
            task = asyncio.create_task(
                _await_outcome(awaitable),
                name=(f"pyruntimekit:{context.run_id.value}:attempt-{context.attempt.value}"),
            )
            outcome = await task
        except Exception as exc:
            failure = Failure.create(
                code=FailureCode("EXECUTOR.ASYNC.EXCEPTION"),
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

        if isinstance(outcome, ExecutionResult):
            return outcome
        return ExecutionResult[object].success(value=outcome)


__all__ = ["AsyncExecutor", "AsyncExecutorClock"]
