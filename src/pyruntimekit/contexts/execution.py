"""Immutable per-attempt execution context."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pyruntimekit.domain.attempt import AttemptNumber
from pyruntimekit.domain.ids import RunId, WorkloadId
from pyruntimekit.domain.validation import (
    freeze_json_mapping,
    plain_json_mapping,
    require_text,
)


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Operational context for one concrete Run attempt."""

    run_id: RunId
    workload_id: WorkloadId
    attempt: AttemptNumber
    correlation_id: str
    trace_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("run_id must be a RunId")
        if not isinstance(self.workload_id, WorkloadId):
            raise TypeError("workload_id must be a WorkloadId")
        if not isinstance(self.attempt, AttemptNumber):
            raise TypeError("attempt must be an AttemptNumber")

        object.__setattr__(
            self,
            "correlation_id",
            require_text(self.correlation_id, field_name="correlation_id"),
        )
        if self.trace_id is not None:
            object.__setattr__(
                self,
                "trace_id",
                require_text(self.trace_id, field_name="trace_id"),
            )
        object.__setattr__(
            self,
            "metadata",
            freeze_json_mapping(self.metadata, field_name="execution metadata"),
        )

    @property
    def identity(self) -> tuple[RunId, AttemptNumber]:
        """Return the operational identity of this execution attempt."""
        return (self.run_id, self.attempt)

    def metadata_dict(self) -> dict[str, object]:
        """Return detached metadata suitable for serialization/transport."""
        return plain_json_mapping(self.metadata)


__all__ = ["ExecutionContext"]
