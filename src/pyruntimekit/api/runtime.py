"""Public synchronous Runtime facade for the first executable slice."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from pyruntimekit.application.runner import SimpleRunner
from pyruntimekit.application.submission import SubmissionOutcome, SubmissionService
from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain.ids import WorkloadId
from pyruntimekit.domain.workload import Workload, WorkloadDescriptor
from pyruntimekit.executors.base import ResolvedWorkload
from pyruntimekit.executors.inline import InlineExecutor
from pyruntimekit.kernel import RuntimeKernel

type RuntimeCallable = Callable[[ExecutionContext], object]
type RuntimeClock = Callable[[], datetime]
type SubmittableWorkload = ResolvedWorkload | RuntimeCallable


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _callable_reference(implementation: RuntimeCallable) -> str:
    module = getattr(implementation, "__module__", None)
    qualname = getattr(implementation, "__qualname__", None)

    if not isinstance(module, str) or not module.strip():
        module = type(implementation).__module__
    if not isinstance(qualname, str) or not qualname.strip():
        qualname = type(implementation).__qualname__

    return f"{module}:{qualname}"


def _resolve_submittable(workload: SubmittableWorkload) -> ResolvedWorkload:
    if isinstance(workload, ResolvedWorkload):
        return workload
    if not callable(workload):
        raise TypeError("workload must be a ResolvedWorkload or callable")

    implementation = workload
    domain_workload = Workload(
        workload_id=WorkloadId.new(),
        descriptor=WorkloadDescriptor(
            kind="python.callable",
            reference=_callable_reference(implementation),
        ),
    )
    return ResolvedWorkload(
        workload=domain_workload,
        implementation=implementation,
    )


class Runtime:
    """Synchronous local Runtime facade backed by InlineExecutor."""

    __slots__ = ("_submission",)

    def __init__(self, *, clock: RuntimeClock = _utc_now) -> None:
        if not callable(clock):
            raise TypeError("clock must be callable")

        kernel = RuntimeKernel()
        executor = InlineExecutor(clock=clock)
        runner = SimpleRunner(
            kernel=kernel,
            executor=executor,
            clock=clock,
        )
        self._submission = SubmissionService(
            kernel=kernel,
            runner=runner,
            clock=clock,
        )

    def submit(
        self,
        workload: SubmittableWorkload,
        *,
        correlation_id: str | None = None,
        trace_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> SubmissionOutcome:
        """Submit and execute synchronously in the first local bootstrap slice."""
        resolved = _resolve_submittable(workload)
        return self._submission.submit(
            resolved,
            correlation_id=correlation_id,
            trace_id=trace_id,
            metadata=metadata,
        )


__all__ = [
    "Runtime",
    "RuntimeCallable",
    "RuntimeClock",
    "SubmittableWorkload",
]
