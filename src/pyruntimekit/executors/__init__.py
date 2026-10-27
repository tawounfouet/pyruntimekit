"""Executor contracts.

Concrete backends stay in their dedicated modules so importing a contract
module does not eagerly load backend implementations.
"""

from .base import (
    AsyncExecutorContract,
    Executor,
    ExecutorDescriptor,
    ResolvedAsyncCallable,
    ResolvedAsyncWorkload,
    ResolvedCallable,
    ResolvedWorkload,
    ThreadExecutorContract,
)
from .capabilities import (
    ASYNC_EXECUTOR_CAPABILITIES,
    INLINE_EXECUTOR_CAPABILITIES,
    THREAD_EXECUTOR_CAPABILITIES,
    ExecutorCapabilities,
    ExecutorCapability,
)

__all__ = [
    "ASYNC_EXECUTOR_CAPABILITIES",
    "INLINE_EXECUTOR_CAPABILITIES",
    "AsyncExecutorContract",
    "Executor",
    "ExecutorCapabilities",
    "ExecutorCapability",
    "ExecutorDescriptor",
    "ResolvedAsyncCallable",
    "ResolvedAsyncWorkload",
    "ResolvedCallable",
    "ResolvedWorkload",
    "THREAD_EXECUTOR_CAPABILITIES",
    "ThreadExecutorContract",
]
