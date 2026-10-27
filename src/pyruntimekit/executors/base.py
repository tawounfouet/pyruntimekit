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
class SubprocessCommand:
    """Explicit immutable command boundary for one OS subprocess."""

    argv: tuple[str, ...]
    cwd: str | None = None
    env: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.argv, tuple):
            raise TypeError("argv must be a tuple of strings")
        if not self.argv:
            raise ValueError("argv must contain at least one argument")
        if not all(isinstance(value, str) for value in self.argv):
            raise TypeError("argv must contain only strings")
        if not self.argv[0].strip():
            raise ValueError("argv[0] must be a non-empty executable")

        if self.cwd is not None:
            object.__setattr__(self, "cwd", require_text(self.cwd, field_name="cwd"))

        if not isinstance(self.env, tuple):
            raise TypeError("env must be a tuple of key/value pairs")
        for entry in self.env:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise TypeError("env must contain only (key, value) pairs")
            key, value = entry
            require_text(key, field_name="env key")
            if not isinstance(value, str):
                raise TypeError("env values must be strings")


@dataclass(frozen=True, slots=True)
class ResolvedSubprocessWorkload:
    """Declarative Workload paired with an explicit OS subprocess command."""

    workload: Workload
    command: SubprocessCommand

    def __post_init__(self) -> None:
        if not isinstance(self.workload, Workload):
            raise TypeError("workload must be a Workload")
        if not isinstance(self.command, SubprocessCommand):
            raise TypeError("command must be a SubprocessCommand")

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


class ThreadExecutorContract(Protocol):
    """Awaitable contract for offloading synchronous Workloads to threads."""

    @property
    def descriptor(self) -> ExecutorDescriptor: ...

    async def execute(
        self,
        workload: ResolvedWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]: ...


class ProcessExecutorContract(Protocol):
    """Awaitable contract for executing synchronous Workloads in child processes."""

    @property
    def descriptor(self) -> ExecutorDescriptor: ...

    async def execute(
        self,
        workload: ResolvedWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]: ...


class SubprocessExecutorContract(Protocol):
    """Awaitable contract for executing explicit OS subprocess commands."""

    @property
    def descriptor(self) -> ExecutorDescriptor: ...

    async def execute(
        self,
        workload: ResolvedSubprocessWorkload,
        context: ExecutionContext,
    ) -> ExecutionResult[object]: ...


__all__ = [
    "AsyncExecutorContract",
    "Executor",
    "ExecutorDescriptor",
    "ProcessExecutorContract",
    "ResolvedAsyncCallable",
    "ResolvedAsyncWorkload",
    "ResolvedCallable",
    "ResolvedSubprocessWorkload",
    "ResolvedWorkload",
    "SubprocessCommand",
    "SubprocessExecutorContract",
    "ThreadExecutorContract",
]
