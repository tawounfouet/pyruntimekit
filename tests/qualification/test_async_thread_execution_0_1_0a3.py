"""Transverse execution qualification for PyRuntimeKit 0.1.0a3."""

from __future__ import annotations

import asyncio
import contextvars
import threading
from datetime import UTC, datetime
from typing import cast

import pytest

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
from pyruntimekit.executors import ResolvedAsyncWorkload, ResolvedWorkload
from pyruntimekit.executors.async_ import AsyncExecutor
from pyruntimekit.executors.inline import InlineExecutor
from pyruntimekit.executors.thread import ThreadExecutor

NOW = datetime(2026, 10, 27, 17, 0, tzinfo=UTC)


def _workload(*, async_kind: bool = False) -> Workload:
    return Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.async_callable" if async_kind else "python.callable",
            reference="tests.qualification.async_thread:work",
        ),
    )


def _context(workload: Workload, label: str) -> ExecutionContext:
    return ExecutionContext(
        run_id=RunId.new(),
        workload_id=workload.workload_id,
        attempt=AttemptNumber.first(),
        correlation_id=label,
    )


def test_a3_inline_async_thread_success_paths_are_compatible() -> None:
    async def scenario() -> None:
        inline_workload = _workload()
        inline_result = InlineExecutor(clock=lambda: NOW).execute(
            ResolvedWorkload(
                workload=inline_workload,
                implementation=lambda context: context.correlation_id,
            ),
            _context(inline_workload, "inline"),
        )

        async_workload = _workload(async_kind=True)

        async def async_implementation(context: ExecutionContext) -> object:
            return context.correlation_id

        async_result = await AsyncExecutor(clock=lambda: NOW).execute(
            ResolvedAsyncWorkload(
                workload=async_workload,
                implementation=async_implementation,
            ),
            _context(async_workload, "async"),
        )

        thread_workload = _workload()
        thread_executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)
        try:
            thread_result = await thread_executor.execute(
                ResolvedWorkload(
                    workload=thread_workload,
                    implementation=lambda context: context.correlation_id,
                ),
                _context(thread_workload, "thread"),
            )
        finally:
            thread_executor.close()

        assert inline_result.succeeded
        assert async_result.succeeded
        assert thread_result.succeeded
        assert (
            inline_result.value,
            async_result.value,
            thread_result.value,
        ) == ("inline", "async", "thread")

    asyncio.run(scenario())


def test_a3_async_contextvars_propagate_and_isolate_concurrent_tasks() -> None:
    marker: contextvars.ContextVar[str] = contextvars.ContextVar(
        "a3_async_qualification_marker",
        default="root",
    )

    async def scenario() -> None:
        executor = AsyncExecutor(max_concurrency=2, clock=lambda: NOW)

        async def run_one(label: str) -> tuple[str, str]:
            workload = _workload(async_kind=True)
            token = marker.set(label)

            async def implementation(context: ExecutionContext) -> object:
                before = marker.get()
                marker.set(f"{context.correlation_id}-inside")
                await asyncio.sleep(0)
                return (before, marker.get())

            try:
                result = await executor.execute(
                    ResolvedAsyncWorkload(
                        workload=workload,
                        implementation=implementation,
                    ),
                    _context(workload, label),
                )
                return cast(tuple[str, str], result.value)
            finally:
                marker.reset(token)

        first, second = await asyncio.gather(run_one("first"), run_one("second"))

        assert first == ("first", "first-inside")
        assert second == ("second", "second-inside")
        assert marker.get() == "root"

    asyncio.run(scenario())


def test_a3_thread_contextvars_propagate_without_worker_leakage() -> None:
    marker: contextvars.ContextVar[str] = contextvars.ContextVar(
        "a3_thread_qualification_marker",
        default="root",
    )

    async def scenario() -> None:
        executor = ThreadExecutor(max_workers=1, max_in_flight=1, clock=lambda: NOW)

        async def run_one(label: str) -> tuple[str, str, int]:
            workload = _workload()
            token = marker.set(label)

            def implementation(context: ExecutionContext) -> object:
                before = marker.get()
                marker.set(f"{context.correlation_id}-inside")
                return (before, marker.get(), threading.get_ident())

            try:
                result = await executor.execute(
                    ResolvedWorkload(
                        workload=workload,
                        implementation=implementation,
                    ),
                    _context(workload, label),
                )
                return cast(tuple[str, str, int], result.value)
            finally:
                marker.reset(token)

        try:
            first = await run_one("first")
            second = await run_one("second")
        finally:
            executor.close()

        assert first[:2] == ("first", "first-inside")
        assert second[:2] == ("second", "second-inside")
        assert first[2] == second[2]
        assert marker.get() == "root"

    asyncio.run(scenario())


def test_a3_async_capacity_applies_backpressure_and_releases_slot() -> None:
    async def scenario() -> None:
        executor = AsyncExecutor(max_concurrency=1, clock=lambda: NOW)
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        release_first = asyncio.Event()

        async def submit(
            label: str,
            *,
            block: bool,
        ) -> ExecutionResult[object]:
            workload = _workload(async_kind=True)

            async def implementation(context: ExecutionContext) -> object:
                (first_started if label == "first" else second_started).set()
                if block:
                    await release_first.wait()
                return context.correlation_id

            return await executor.execute(
                ResolvedAsyncWorkload(
                    workload=workload,
                    implementation=implementation,
                ),
                _context(workload, label),
            )

        first = asyncio.create_task(submit("first", block=True))
        await asyncio.wait_for(first_started.wait(), timeout=1)
        second = asyncio.create_task(submit("second", block=False))
        await asyncio.sleep(0)

        assert executor.current_load == 1
        assert not second_started.is_set()
        assert not second.done()

        release_first.set()
        first_result, second_result = await asyncio.gather(first, second)

        assert first_result.value == "first"
        assert second_result.value == "second"
        assert second_started.is_set()
        assert executor.current_load == 0

    asyncio.run(scenario())


def test_a3_thread_capacity_applies_backpressure_until_backend_completion() -> None:
    async def scenario() -> None:
        executor = ThreadExecutor(
            max_workers=1,
            max_in_flight=1,
            clock=lambda: NOW,
        )
        first_started = threading.Event()
        second_started = threading.Event()
        release_first = threading.Event()

        first_workload = _workload()
        second_workload = _workload()

        def first_implementation(context: ExecutionContext) -> object:
            first_started.set()
            release_first.wait(timeout=2)
            return context.correlation_id

        def second_implementation(context: ExecutionContext) -> object:
            second_started.set()
            return context.correlation_id

        first = asyncio.create_task(
            executor.execute(
                ResolvedWorkload(
                    workload=first_workload,
                    implementation=first_implementation,
                ),
                _context(first_workload, "first"),
            )
        )

        try:
            for _ in range(200):
                if first_started.is_set():
                    break
                await asyncio.sleep(0.001)

            assert first_started.is_set()
            assert executor.current_load == 1

            second = asyncio.create_task(
                executor.execute(
                    ResolvedWorkload(
                        workload=second_workload,
                        implementation=second_implementation,
                    ),
                    _context(second_workload, "second"),
                )
            )
            await asyncio.sleep(0.01)

            assert not second_started.is_set()
            assert executor.current_load == 1

            release_first.set()
            first_result, second_result = await asyncio.gather(first, second)
            await asyncio.sleep(0)

            assert first_result.value == "first"
            assert second_result.value == "second"
            assert second_started.is_set()
            assert executor.current_load == 0
        finally:
            release_first.set()
            executor.close()

    asyncio.run(scenario())


def test_a3_async_and_thread_failures_remain_normalized_and_safe() -> None:
    async def scenario() -> None:
        async_workload = _workload(async_kind=True)

        async def async_failure(context: ExecutionContext) -> object:
            raise ValueError(f"async failure: {context.correlation_id}")

        async_result = await AsyncExecutor(clock=lambda: NOW).execute(
            ResolvedAsyncWorkload(
                workload=async_workload,
                implementation=async_failure,
            ),
            _context(async_workload, "qualification"),
        )

        thread_workload = _workload()

        def thread_failure(context: ExecutionContext) -> object:
            raise RuntimeError(f"thread failure: {context.correlation_id}")

        thread_executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)
        try:
            thread_result = await thread_executor.execute(
                ResolvedWorkload(
                    workload=thread_workload,
                    implementation=thread_failure,
                ),
                _context(thread_workload, "qualification"),
            )
        finally:
            thread_executor.close()

        for result, code, cause_type in (
            (async_result, "EXECUTOR.ASYNC.EXCEPTION", "ValueError"),
            (thread_result, "EXECUTOR.THREAD.EXCEPTION", "RuntimeError"),
        ):
            assert result.failed
            assert result.failure is not None
            assert result.failure.code.value == code
            assert result.failure.category is FailureCategory.EXECUTION
            assert result.failure.origin is FailureOrigin.EXECUTOR
            assert result.failure.scope is FailureScope.ATTEMPT
            assert result.failure.cause is not None
            assert result.failure.cause.type_name == cause_type
            assert result.failure.traceback_ref is None

    asyncio.run(scenario())


def test_a3_async_cancellation_propagates_and_releases_capacity() -> None:
    async def scenario() -> None:
        executor = AsyncExecutor(max_concurrency=1, clock=lambda: NOW)
        workload = _workload(async_kind=True)
        started = asyncio.Event()
        blocker = asyncio.Event()

        async def implementation(context: ExecutionContext) -> object:
            started.set()
            await blocker.wait()
            return context.correlation_id

        task = asyncio.create_task(
            executor.execute(
                ResolvedAsyncWorkload(
                    workload=workload,
                    implementation=implementation,
                ),
                _context(workload, "cancel-async"),
            )
        )
        await asyncio.wait_for(started.wait(), timeout=1)
        assert executor.current_load == 1

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert executor.current_load == 0

    asyncio.run(scenario())


def test_a3_cancelled_thread_await_does_not_claim_thread_termination() -> None:
    async def scenario() -> None:
        executor = ThreadExecutor(
            max_workers=1,
            max_in_flight=1,
            clock=lambda: NOW,
        )
        workload = _workload()
        started = threading.Event()
        release = threading.Event()
        completed = threading.Event()

        def implementation(context: ExecutionContext) -> object:
            started.set()
            release.wait(timeout=2)
            completed.set()
            return context.correlation_id

        task = asyncio.create_task(
            executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=implementation,
                ),
                _context(workload, "cancel-thread"),
            )
        )

        try:
            for _ in range(200):
                if started.is_set():
                    break
                await asyncio.sleep(0.001)

            assert started.is_set()
            assert executor.current_load == 1

            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

            assert not completed.is_set()
            assert executor.current_load == 1

            release.set()
            for _ in range(200):
                if completed.is_set() and executor.current_load == 0:
                    break
                await asyncio.sleep(0.001)

            assert completed.is_set()
            assert executor.current_load == 0
        finally:
            release.set()
            executor.close()

    asyncio.run(scenario())


def test_a3_thread_cleanup_is_explicit_idempotent_and_prevents_reuse() -> None:
    async def scenario() -> None:
        executor = ThreadExecutor(max_workers=1, clock=lambda: NOW)
        executor.close()
        executor.close()

        workload = _workload()
        with pytest.raises(RuntimeError, match="closed"):
            await executor.execute(
                ResolvedWorkload(
                    workload=workload,
                    implementation=lambda context: context.correlation_id,
                ),
                _context(workload, "closed"),
            )

    asyncio.run(scenario())
