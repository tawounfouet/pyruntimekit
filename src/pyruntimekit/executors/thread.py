"""Thread-backed local Executor backend."""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Callable
from contextlib import suppress
from concurrent.futures import Future, ThreadPoolExecutor
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
from .capabilities import THREAD_EXECUTOR_CAPABILITIES

type ThreadExecutorClock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _invoke_workload_in_context(
    ambient_context: contextvars.Context,
    workload: ResolvedWorkload,
    context: ExecutionContext,
) -> object:
    return ambient_context.run(workload.implementation, context)


class ThreadExecutor:
    """Execute synchronous Workloads with bounded submission to an owned thread pool."""

    __slots__ = (
        "_capacity",
        "_clock",
        "_closed",
        "_current_load",
        "_max_in_flight",
        "_pool",
    )

    _DESCRIPTOR = ExecutorDescriptor(
        name="thread.default",
        kind="thread",
        capabilities=THREAD_EXECUTOR_CAPABILITIES,
    )

    def __init__(
        self,
        *,
        max_workers: int | None = None,
        max_in_flight: int = 32,
        clock: ThreadExecutorClock = _utc_now,
    ) -> None:
        if max_workers is not None:
            if isinstance(max_workers, bool) or not isinstance(max_workers, int):
                raise TypeError("max_workers must be an int or None")
            if max_workers < 1:
                raise ValueError("max_workers must be >= 1")
        if isinstance(max_in_flight, bool) or not isinstance(max_in_flight, int):
            raise TypeError("max_in_flight must be an int")
        if max_in_flight < 1:
            raise ValueError("max_in_flight must be >= 1")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self._clock = clock
        self._closed = False
        self._max_in_flight = max_in_flight
        self._current_load = 0
        self._capacity = asyncio.BoundedSemaphore(max_in_flight)
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pyruntimekit-thread",
        )

    @property
    def descriptor(self) -> ExecutorDescriptor:
        """Describe the guarantees currently implemented by ThreadExecutor."""
        return self._DESCRIPTOR

    @property
    def max_in_flight(self) -> int:
        """Return the maximum number of submitted or running thread executions."""
        return self._max_in_flight

    @property
    def current_load(self) -> int:
        """Return the number of backend Futures currently holding capacity."""
        return self._current_load

    async def execute(
        self,
        workload: ResolvedWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]:
        """Submit one synchronous Workload only after bounded capacity is available."""
        if not isinstance(workload, ResolvedWorkload):
            raise TypeError("workload must be a ResolvedWorkload")
        if not isinstance(context, ExecutionContext):
            raise TypeError("context must be an ExecutionContext")
        if workload.workload_id != context.workload_id:
            raise ValueError("ResolvedWorkload and ExecutionContext must share workload_id")
        if self._closed:
            raise RuntimeError("ThreadExecutor is closed")

        await self._capacity.acquire()
        if self._closed:
            self._capacity.release()
            raise RuntimeError("ThreadExecutor is closed")

        self._current_load += 1
        loop = asyncio.get_running_loop()
        ambient_context = contextvars.copy_context()

        try:
            concurrent_future = self._pool.submit(
                _invoke_workload_in_context,
                ambient_context,
                workload,
                context,
            )
        except Exception as exc:
            self._release_capacity()
            return self._failure_result(exc, workload)

        concurrent_future.add_done_callback(
            lambda future: self._schedule_capacity_release(loop, future)
        )

        try:
            outcome = await asyncio.wrap_future(concurrent_future, loop=loop)
        except Exception as exc:
            return self._failure_result(exc, workload)

        if isinstance(outcome, ExecutionResult):
            return outcome
        return ExecutionResult[object].success(value=outcome)

    def _schedule_capacity_release(
        self,
        loop: asyncio.AbstractEventLoop,
        future: Future[object],
    ) -> None:
        del future
        with suppress(RuntimeError):
            loop.call_soon_threadsafe(self._release_capacity)

    def _release_capacity(self) -> None:
        if self._current_load < 1:
            return
        self._current_load -= 1
        self._capacity.release()

    def _failure_result(
        self,
        exc: Exception,
        workload: ResolvedWorkload,
    ) -> ExecutionResult[object]:
        failure = Failure.create(
            code=FailureCode("EXECUTOR.THREAD.EXCEPTION"),
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
        """Shut down the owned thread pool once."""
        if self._closed:
            return
        self._closed = True
        self._pool.shutdown(
            wait=wait,
            cancel_futures=cancel_futures,
        )


__all__ = ["ThreadExecutor", "ThreadExecutorClock"]
