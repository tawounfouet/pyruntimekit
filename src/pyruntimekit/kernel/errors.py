"""RuntimeKernel-specific errors."""

from __future__ import annotations


class RuntimeKernelError(ValueError):
    """Base error for RuntimeKernel command/decision violations."""


class InvalidKernelCommandError(RuntimeKernelError):
    """Raised when RuntimeKernel receives an unsupported command value."""


class KernelInvariantError(RuntimeKernelError):
    """Raised when a Kernel-specific lifecycle invariant is violated."""


__all__ = [
    "InvalidKernelCommandError",
    "KernelInvariantError",
    "RuntimeKernelError",
]
