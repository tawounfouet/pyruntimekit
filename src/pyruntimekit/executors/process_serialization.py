"""Explicit serialization boundary for ProcessExecutor."""

from __future__ import annotations

import pickle

from pyruntimekit.contexts import ExecutionContext

from .base import ResolvedWorkload


class ProcessResultSerializationError(Exception):
    """Serializable marker for a child result that cannot cross the process boundary."""

    def __init__(self, type_name: str, message: str | None) -> None:
        self.type_name = type_name
        self.cause_message = message
        super().__init__(type_name, message)


def preflight_process_submission(
    workload: ResolvedWorkload,
    context: ExecutionContext,
) -> None:
    """Verify that the complete process submission can cross a pickle boundary."""
    pickle.dumps(
        (workload, context),
        protocol=pickle.HIGHEST_PROTOCOL,
    )


def serialize_process_result(value: object) -> bytes:
    """Serialize one child-process outcome or raise a transport-safe marker."""
    try:
        return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as exc:
        raise ProcessResultSerializationError(
            type(exc).__name__,
            str(exc) or None,
        ) from None


def deserialize_process_result(payload: bytes) -> object:
    """Deserialize one explicitly serialized child-process outcome."""
    return pickle.loads(payload)


__all__ = [
    "ProcessResultSerializationError",
    "deserialize_process_result",
    "preflight_process_submission",
    "serialize_process_result",
]
