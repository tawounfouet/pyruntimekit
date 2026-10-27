"""Executor capability contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ExecutorCapability(StrEnum):
    """Stable capability promises exposed by execution backends."""

    IN_PROCESS = "IN_PROCESS"
    SHARED_MEMORY = "SHARED_MEMORY"
    TRUSTED_ONLY = "TRUSTED_ONLY"
    ASYNC_EXECUTION = "ASYNC_EXECUTION"
    THREAD_EXECUTION = "THREAD_EXECUTION"
    PROCESS_EXECUTION = "PROCESS_EXECUTION"
    SUBPROCESS_EXECUTION = "SUBPROCESS_EXECUTION"
    PROCESS_ISOLATION = "PROCESS_ISOLATION"
    SERIALIZED_BOUNDARY = "SERIALIZED_BOUNDARY"
    CONTEXTVARS_PROPAGATION = "CONTEXTVARS_PROPAGATION"
    THREAD_CONTEXT_PROPAGATION = "THREAD_CONTEXT_PROPAGATION"
    BOUNDED_CAPACITY = "BOUNDED_CAPACITY"


@dataclass(frozen=True, slots=True)
class ExecutorCapabilities:
    """Immutable set of capabilities guaranteed by an Executor."""

    values: frozenset[ExecutorCapability] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.values, frozenset):
            raise TypeError("values must be a frozenset of ExecutorCapability values")
        if not all(isinstance(value, ExecutorCapability) for value in self.values):
            raise TypeError("values must contain only ExecutorCapability values")

    def supports(self, capability: ExecutorCapability) -> bool:
        """Return whether the capability is explicitly guaranteed."""
        if not isinstance(capability, ExecutorCapability):
            raise TypeError("capability must be an ExecutorCapability")
        return capability in self.values


INLINE_EXECUTOR_CAPABILITIES = ExecutorCapabilities(
    frozenset(
        {
            ExecutorCapability.IN_PROCESS,
            ExecutorCapability.SHARED_MEMORY,
            ExecutorCapability.TRUSTED_ONLY,
        }
    )
)

ASYNC_EXECUTOR_CAPABILITIES = ExecutorCapabilities(
    frozenset(
        {
            ExecutorCapability.IN_PROCESS,
            ExecutorCapability.SHARED_MEMORY,
            ExecutorCapability.TRUSTED_ONLY,
            ExecutorCapability.ASYNC_EXECUTION,
            ExecutorCapability.CONTEXTVARS_PROPAGATION,
            ExecutorCapability.BOUNDED_CAPACITY,
        }
    )
)

THREAD_EXECUTOR_CAPABILITIES = ExecutorCapabilities(
    frozenset(
        {
            ExecutorCapability.IN_PROCESS,
            ExecutorCapability.SHARED_MEMORY,
            ExecutorCapability.TRUSTED_ONLY,
            ExecutorCapability.THREAD_EXECUTION,
            ExecutorCapability.THREAD_CONTEXT_PROPAGATION,
            ExecutorCapability.BOUNDED_CAPACITY,
        }
    )
)


__all__ = [
    "ASYNC_EXECUTOR_CAPABILITIES",
    "INLINE_EXECUTOR_CAPABILITIES",
    "THREAD_EXECUTOR_CAPABILITIES",
    "ExecutorCapabilities",
    "ExecutorCapability",
]
