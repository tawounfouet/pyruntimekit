"""Executor contracts for synchronous and asynchronous local execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from pyruntimekit.contexts import ExecutionContext
from pyruntimekit.domain.ids import WorkloadId
from pyruntimekit.domain.result import ExecutionResult
from pyruntimekit.domain.validation import require_text
from pyruntimekit.domain.workload import Workload

from .capabilities import ExecutorCapabilities

type ResolvedCallable = Callable[[ExecutionContext], object]
type ResolvedAsyncCallable = Callable[[ExecutionContext], Awaitable[object]]


@dataclass(frozen=True, slots=True)
class ResolvedWorkload:
    """Declarative Workload paired with an already-resolved sync implementation."""

    workload: Workload
    implementation: ResolvedCallable

    def __post_init__(self) -> None:
        if not isinstance(self.workload, Workload):
            raise TypeError("workload must be a Workload")
        if not callable(self.implementation):
            raise TypeError("implementation must be callable")

    @property
    def workload_id(self) -> WorkloadId:
        """Return the identity of the declarative Workload."""
        return self.workload.workload_id


@dataclass(frozen=True, slots=True)
class ResolvedAsyncWorkload:
    """Declarative Workload paired with an already-resolved awaitable implementation."""

    workload: Workload
    implementation: ResolvedAsyncCallable

    def __post_init__(self) -> None:
        if not isinstance(self.workload, Workload):
            raise TypeError("workload must be a Workload")
        if not callable(self.implementation):
            raise TypeError("implementation must be callable")

    @property
    def workload_id(self) -> WorkloadId:
        """Return the identity of the declarative Workload."""
        return self.workload.workload_id


@dataclass(frozen=True, slots=True)
class ExecutorDescriptor:
    """Small introspection descriptor for one logical Executor configuration."""

    name: str
    kind: str
    capabilities: ExecutorCapabilities

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_text(self.name, field_name="name"))
        object.__setattr__(self, "kind", require_text(self.kind, field_name="kind"))
        if not isinstance(self.capabilities, ExecutorCapabilities):
            raise TypeError("capabilities must be ExecutorCapabilities")


class Executor(Protocol):
    """Synchronous Executor contract retained from the 0.1.0a2 slice."""

    @property
    def descriptor(self) -> ExecutorDescriptor: ...

    def execute(
        self,
        workload: ResolvedWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]: ...


class AsyncExecutorContract(Protocol):
    """Awaitable Executor contract for asynchronous execution backends."""

    @property
    def descriptor(self) -> ExecutorDescriptor: ...

    async def execute(
        self,
        workload: ResolvedAsyncWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]: ...


__all__ = [
    "AsyncExecutorContract",
    "Executor",
    "ExecutorDescriptor",
    "ResolvedAsyncCallable",
    "ResolvedAsyncWorkload",
    "ResolvedCallable",
    "ResolvedWorkload",
]
