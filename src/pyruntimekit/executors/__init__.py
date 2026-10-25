"""Executor contracts.

Concrete backends stay in their dedicated modules so importing a contract
module does not eagerly load backend implementations.
"""

from .base import Executor, ExecutorDescriptor, ResolvedCallable, ResolvedWorkload
from .capabilities import (
    INLINE_EXECUTOR_CAPABILITIES,
    ExecutorCapabilities,
    ExecutorCapability,
)

__all__ = [
    "INLINE_EXECUTOR_CAPABILITIES",
    "Executor",
    "ExecutorCapabilities",
    "ExecutorCapability",
    "ExecutorDescriptor",
    "ResolvedCallable",
    "ResolvedWorkload",
]
