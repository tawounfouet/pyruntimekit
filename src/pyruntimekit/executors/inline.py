"""Deterministic in-process InlineExecutor."""

from __future__ import annotations

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
from pyruntimekit.executors.base import ExecutorDescriptor, ResolvedWorkload
from pyruntimekit.executors.capabilities import INLINE_EXECUTOR_CAPABILITIES


type ExecutorClock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class InlineExecutor:
    """Execute a resolved callable directly in the current process and thread."""

    __slots__ = ("_clock",)

    _DESCRIPTOR = ExecutorDescriptor(
        name="inline.default",
        kind="inline",
        capabilities=INLINE_EXECUTOR_CAPABILITIES,
    )

    def __init__(self, *, clock: ExecutorClock = _utc_now) -> None:
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._clock = clock

    @property
    def descriptor(self) -> ExecutorDescriptor:
        """Describe the guarantees of this InlineExecutor."""
        return self._DESCRIPTOR

    def execute(
        self,
        workload: ResolvedWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]:
        """Execute once inline and normalize ordinary Python exceptions."""
        if not isinstance(workload, ResolvedWorkload):
            raise TypeError("workload must be a ResolvedWorkload")
        if not isinstance(context, ExecutionContext):
            raise TypeError("context must be an ExecutionContext")
        if workload.workload_id != context.workload_id:
            raise ValueError("ResolvedWorkload and ExecutionContext must share workload_id")

        try:
            outcome = workload.implementation(context)
        except Exception as exc:
            failure = Failure.create(
                code=FailureCode("EXECUTOR.INLINE.EXCEPTION"),
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


__all__ = ["ExecutorClock", "InlineExecutor"]
