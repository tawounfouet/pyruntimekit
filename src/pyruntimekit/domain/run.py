"""Run aggregate and persistence-neutral snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .enums import RunState
from .ids import RunId, WorkloadId
from .validation import (
    datetime_from_utc_iso,
    datetime_to_utc_iso,
    freeze_json_mapping,
    normalize_aware_datetime,
    plain_json_mapping,
)


RUN_SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True, order=True, slots=True)
class RunVersion:
    """Monotone optimistic-concurrency version for a Run."""

    value: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("run version must be an integer")
        if self.value < 0:
            raise ValueError("run version must be greater than or equal to zero")

    @classmethod
    def initial(cls) -> RunVersion:
        """Return the initial version of a newly created Run."""
        return cls(0)

    def next(self) -> RunVersion:
        """Return the next monotone version."""
        return type(self)(self.value + 1)


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    """Immutable versioned representation of Run state for persistence/audit."""

    schema_version: int
    run_id: str
    workload_id: str
    state: str
    version: int
    created_at: str
    updated_at: str
    current_attempt: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int):
            raise TypeError("schema_version must be an integer")
        if self.schema_version <= 0:
            raise ValueError("schema_version must be greater than zero")
        RunId.from_str(self.run_id)
        WorkloadId.from_str(self.workload_id)
        RunState(self.state)
        RunVersion(self.version)
        created = datetime_from_utc_iso(self.created_at, field_name="created_at")
        updated = datetime_from_utc_iso(self.updated_at, field_name="updated_at")
        if updated < created:
            raise ValueError("updated_at must not be earlier than created_at")
        if self.current_attempt is not None:
            if isinstance(self.current_attempt, bool) or not isinstance(self.current_attempt, int):
                raise TypeError("current_attempt must be an integer or None")
            if self.current_attempt < 1:
                raise ValueError("current_attempt must be greater than or equal to one")
        object.__setattr__(
            self,
            "metadata",
            freeze_json_mapping(self.metadata, field_name="metadata"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a detached serialization-friendly snapshot mapping."""
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "workload_id": self.workload_id,
            "state": self.state,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_attempt": self.current_attempt,
            "metadata": plain_json_mapping(self.metadata),
        }


class Run:
    """Principal mutable Aggregate Root for one logical Workload execution."""

    __slots__ = (
        "_created_at",
        "_current_attempt",
        "_metadata",
        "_run_id",
        "_state",
        "_updated_at",
        "_version",
        "_workload_id",
    )

    def __init__(
        self,
        *,
        run_id: RunId,
        workload_id: WorkloadId,
        created_at: datetime,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        timestamp = normalize_aware_datetime(created_at, field_name="created_at")
        self._run_id = run_id
        self._workload_id = workload_id
        self._state = RunState.CREATED
        self._version = RunVersion.initial()
        self._created_at = timestamp
        self._updated_at = timestamp
        self._current_attempt: int | None = None
        self._metadata = freeze_json_mapping(metadata, field_name="metadata")

    @classmethod
    def create(
        cls,
        workload_id: WorkloadId,
        *,
        run_id: RunId | None = None,
        created_at: datetime | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Run:
        """Create a new Run in the canonical CREATED state."""
        return cls(
            run_id=RunId.new() if run_id is None else run_id,
            workload_id=workload_id,
            created_at=datetime.now(UTC) if created_at is None else created_at,
            metadata=metadata,
        )

    @classmethod
    def from_snapshot(cls, snapshot: RunSnapshot) -> Run:
        """Restore a Run from a supported immutable snapshot."""
        if snapshot.schema_version != RUN_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported RunSnapshot schema_version")

        run = cls(
            run_id=RunId.from_str(snapshot.run_id),
            workload_id=WorkloadId.from_str(snapshot.workload_id),
            created_at=datetime_from_utc_iso(snapshot.created_at, field_name="created_at"),
            metadata=snapshot.metadata,
        )
        run._state = RunState(snapshot.state)
        run._version = RunVersion(snapshot.version)
        run._updated_at = datetime_from_utc_iso(snapshot.updated_at, field_name="updated_at")
        run._current_attempt = snapshot.current_attempt
        return run

    @property
    def run_id(self) -> RunId:
        return self._run_id

    @property
    def workload_id(self) -> WorkloadId:
        return self._workload_id

    @property
    def state(self) -> RunState:
        return self._state

    @property
    def version(self) -> RunVersion:
        return self._version

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def current_attempt(self) -> int | None:
        return self._current_attempt

    @property
    def metadata(self) -> Mapping[str, object]:
        return self._metadata

    @property
    def is_terminal(self) -> bool:
        return self._state.is_terminal

    def metadata_dict(self) -> dict[str, object]:
        """Return detached metadata suitable for serialization."""
        return plain_json_mapping(self._metadata)

    def snapshot(self) -> RunSnapshot:
        """Capture the aggregate as an immutable persistence-neutral snapshot."""
        return RunSnapshot(
            schema_version=RUN_SNAPSHOT_SCHEMA_VERSION,
            run_id=self._run_id.value,
            workload_id=self._workload_id.value,
            state=self._state.value,
            version=self._version.value,
            created_at=datetime_to_utc_iso(self._created_at, field_name="created_at"),
            updated_at=datetime_to_utc_iso(self._updated_at, field_name="updated_at"),
            current_attempt=self._current_attempt,
            metadata=self._metadata,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Run):
            return NotImplemented
        return self._run_id == other._run_id

    def __hash__(self) -> int:
        return hash(self._run_id)

    def __repr__(self) -> str:
        return (
            "Run("
            f"run_id={self._run_id!r}, "
            f"workload_id={self._workload_id!r}, "
            f"state={self._state.value!r}, "
            f"version={self._version.value}"
            ")"
        )


__all__ = ["RUN_SNAPSHOT_SCHEMA_VERSION", "Run", "RunSnapshot", "RunVersion"]
