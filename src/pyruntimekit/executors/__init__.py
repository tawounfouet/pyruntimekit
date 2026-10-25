"""Execution backend contracts and built-in Executors."""

from .base import Executor, ExecutorDescriptor, ResolvedCallable, ResolvedWorkload
from .capabilities import (
    INLINE_EXECUTOR_CAPABILITIES,
    ExecutorCapabilities,
    ExecutorCapability,
)
from .inline import ExecutorClock, InlineExecutor

__all__ = [
    "Executor",
    "ExecutorCapabilities",
    "ExecutorCapability",
    "ExecutorClock",
    "ExecutorDescriptor",
    "INLINE_EXECUTOR_CAPABILITIES",
    "InlineExecutor",
    "ResolvedCallable",
    "ResolvedWorkload",
]
