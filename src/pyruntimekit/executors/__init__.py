"""Executor contracts.

Concrete backends stay in their dedicated modules so importing a contract
module does not eagerly load backend implementations.
"""

from .base import (
    AsyncExecutorContract,
    Executor,
    ExecutorDescriptor,
    ProcessExecutorContract,
    ResolvedAsyncCallable,
    ResolvedAsyncWorkload,
    ResolvedCallable,
    ResolvedSubprocessWorkload,
    ResolvedWorkload,
    SubprocessCommand,
    SubprocessExecutorContract,
    ThreadExecutorContract,
)
from .capabilities import (
    ASYNC_EXECUTOR_CAPABILITIES,
    INLINE_EXECUTOR_CAPABILITIES,
    PROCESS_EXECUTOR_CAPABILITIES,
    THREAD_EXECUTOR_CAPABILITIES,
    ExecutorCapabilities,
    ExecutorCapability,
)

__all__ = [
    "ASYNC_EXECUTOR_CAPABILITIES",
    "INLINE_EXECUTOR_CAPABILITIES",
    "PROCESS_EXECUTOR_CAPABILITIES",
    "THREAD_EXECUTOR_CAPABILITIES",
    "AsyncExecutorContract",
    "Executor",
    "ExecutorCapabilities",
    "ExecutorCapability",
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
