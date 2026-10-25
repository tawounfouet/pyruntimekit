"""Typed identifiers for core PyRuntimeKit domain concepts."""

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, init=False, repr=False)
class _UuidIdentifier:
    """Immutable semantic identifier with an encapsulated UUID backing value."""

    _uuid: UUID

    def __init__(self, value: str) -> None:
        """Build an identifier from a UUID-compatible string value."""
        if not isinstance(value, str):
            raise TypeError("identifier value must be a string")

        try:
            parsed = UUID(value)
        except ValueError as exc:
            raise ValueError("identifier value must be a valid UUID") from exc

        if parsed.int == 0:
            raise ValueError("identifier value must not be the nil UUID")

        object.__setattr__(self, "_uuid", parsed)

    @classmethod
    def new(cls) -> Self:
        """Generate a new identifier."""
        return cls(str(uuid4()))

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Reconstruct an identifier from its serialized string value."""
        return cls(value)

    @property
    def value(self) -> str:
        """Return the stable serialization-friendly scalar value."""
        return str(self._uuid)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self.value}')"


class RunId(_UuidIdentifier):
    """Identity of a runtime Run aggregate."""


class WorkloadId(_UuidIdentifier):
    """Identity of a logical Workload."""


class FailureId(_UuidIdentifier):
    """Identity of a normalized runtime Failure."""


class EventId(_UuidIdentifier):
    """Identity of a domain Event."""


__all__ = ["EventId", "FailureId", "RunId", "WorkloadId"]
