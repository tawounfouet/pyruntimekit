"""Executor capability contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ExecutorCapability(StrEnum):
    """Stable capability promises exposed by execution backends."""

    IN_PROCESS = "IN_PROCESS"
    SHARED_MEMORY = "SHARED_MEMORY"
    TRUSTED_ONLY = "TRUSTED_ONLY"


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


__all__ = [
    "ExecutorCapabilities",
    "ExecutorCapability",
    "INLINE_EXECUTOR_CAPABILITIES",
]
