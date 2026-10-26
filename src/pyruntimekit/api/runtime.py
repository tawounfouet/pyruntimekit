"""Public synchronous Runtime facade for the first executable slice."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from pyruntimekit.application.runner import SimpleRunner
from pyruntimekit.application.submission import SubmissionOutcome, SubmissionService
from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain.enums import RunState
from pyruntimekit.domain.ids import RunId, WorkloadId
from pyruntimekit.domain.result import RunResult
from pyruntimekit.domain.workload import Workload, WorkloadDescriptor
from pyruntimekit.executors.base import ResolvedWorkload
from pyruntimekit.executors.inline import InlineExecutor
from pyruntimekit.kernel import RuntimeKernel

from .run_handle import RunHandle

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


@dataclass(frozen=True, slots=True)
class _CompletedRunRecord:
    """Ephemeral read model retained only for bootstrap RunHandle access."""

    state: RunState
    result: RunResult[object]

    def __post_init__(self) -> None:
        if not self.state.is_terminal:
            raise ValueError("completed Run record requires a terminal RunState")


class _InMemoryRunHandleResolver:
    """Explicit non-durable completed-run read registry."""

    __slots__ = ("_records",)

    def __init__(self) -> None:
        self._records: dict[RunId, _CompletedRunRecord] = {}

    def record(self, outcome: SubmissionOutcome) -> None:
        if not isinstance(outcome, SubmissionOutcome):
            raise TypeError("outcome must be a SubmissionOutcome")
        self._records[outcome.run_id] = _CompletedRunRecord(
            state=outcome.run.state,
            result=outcome.result,
        )

    def status(self, run_id: RunId) -> RunState:
        return self._lookup(run_id).state

    def result(self, run_id: RunId) -> RunResult[object]:
        return self._lookup(run_id).result

    def _lookup(self, run_id: RunId) -> _CompletedRunRecord:
        if not isinstance(run_id, RunId):
            raise TypeError("run_id must be a RunId")
        try:
            return self._records[run_id]
        except KeyError as exc:
            raise LookupError(f"unknown RunId: {run_id.value}") from exc


class Runtime:
    """Synchronous local Runtime facade backed by InlineExecutor."""

    __slots__ = ("_handles", "_submission")

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
        self._handles = _InMemoryRunHandleResolver()

    def submit(
        self,
        workload: SubmittableWorkload,
        *,
        correlation_id: str | None = None,
        trace_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> RunHandle[object]:
        """Submit synchronously and return a client reference to the Run."""
        resolved = _resolve_submittable(workload)
        outcome = self._submission.submit(
            resolved,
            correlation_id=correlation_id,
            trace_id=trace_id,
            metadata=metadata,
        )
        self._handles.record(outcome)
        return RunHandle(
            run_id=outcome.run_id,
            _resolver=self._handles,
        )


__all__ = [
    "Runtime",
    "RuntimeCallable",
    "RuntimeClock",
    "SubmittableWorkload",
]
