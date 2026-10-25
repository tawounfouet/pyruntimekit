"""Backend-neutral execution and logical Run result contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Self

from .failure import Failure
from .ids import ArtifactId
from .validation import (
    freeze_json_mapping,
    normalize_aware_datetime,
    plain_json_mapping,
    require_text,
)

@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Immutable reference to externally stored result material."""

    artifact_id: ArtifactId
    uri: str
    media_type: str | None = None
    checksum: str | None = None
    size: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, ArtifactId):
            raise TypeError("artifact_id must be an ArtifactId")
        object.__setattr__(self, "uri", require_text(self.uri, field_name="uri"))
        if self.media_type is not None:
            object.__setattr__(
                self,
                "media_type",
                require_text(self.media_type, field_name="media_type"),
            )
        if self.checksum is not None:
            object.__setattr__(
                self,
                "checksum",
                require_text(self.checksum, field_name="checksum"),
            )
        if self.size is not None:
            if isinstance(self.size, bool) or not isinstance(self.size, int):
                raise TypeError("size must be an integer or None")
            if self.size < 0:
                raise ValueError("size must be greater than or equal to zero")

    def to_dict(self) -> dict[str, object]:
        """Return a stable serialization-friendly artifact reference."""
        return {
            "artifact_id": self.artifact_id.value,
            "uri": self.uri,
            "media_type": self.media_type,
            "checksum": self.checksum,
            "size": self.size,
        }


@dataclass(frozen=True, slots=True)
class ExecutionResult[T]:
    """Technical backend-neutral result returned by an Executor."""

    value: T | None = None
    failure: Failure | None = None
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.failure is not None and not isinstance(self.failure, Failure):
            raise TypeError("failure must be a Failure or None")
        if self.failure is not None and self.value is not None:
            raise ValueError("a failed ExecutionResult cannot also contain a value")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise TypeError("exit_code must be an integer or None")
        if self.stdout is not None and not isinstance(self.stdout, str):
            raise TypeError("stdout must be a string or None")
        if self.stderr is not None and not isinstance(self.stderr, str):
            raise TypeError("stderr must be a string or None")
        if not isinstance(self.artifacts, tuple):
            raise TypeError("artifacts must be a tuple of ArtifactRef values")
        if not all(isinstance(artifact, ArtifactRef) for artifact in self.artifacts):
            raise TypeError("artifacts must contain only ArtifactRef values")
        object.__setattr__(
            self,
            "metadata",
            freeze_json_mapping(self.metadata, field_name="result metadata"),
        )

    @classmethod
    def success(
        cls,
        value: T | None = None,
        *,
        exit_code: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        artifacts: tuple[ArtifactRef, ...] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> Self:
        """Create a successful execution result."""
        return cls(
            value=value,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            artifacts=artifacts,
            metadata={} if metadata is None else metadata,
        )

    @classmethod
    def from_failure(
        cls,
        failure: Failure,
        *,
        exit_code: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        artifacts: tuple[ArtifactRef, ...] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> Self:
        """Create a failed execution result from a normalized Failure."""
        return cls(
            failure=failure,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            artifacts=artifacts,
            metadata={} if metadata is None else metadata,
        )

    @property
    def succeeded(self) -> bool:
        return self.failure is None

    @property
    def failed(self) -> bool:
        return self.failure is not None

    def metadata_dict(self) -> dict[str, object]:
        """Return detached metadata suitable for serialization."""
        return plain_json_mapping(self.metadata)


@dataclass(frozen=True, slots=True)
class RunResult[T]:
    """Logical final result of a Run."""

    completed_at: datetime
    value: T | None = None
    failure: Failure | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.failure is not None and not isinstance(self.failure, Failure):
            raise TypeError("failure must be a Failure or None")
        if self.failure is not None and self.value is not None:
            raise ValueError("a failed RunResult cannot also contain a value")
        if not isinstance(self.artifacts, tuple):
            raise TypeError("artifacts must be a tuple of ArtifactRef values")
        if not all(isinstance(artifact, ArtifactRef) for artifact in self.artifacts):
            raise TypeError("artifacts must contain only ArtifactRef values")
        object.__setattr__(
            self,
            "completed_at",
            normalize_aware_datetime(self.completed_at, field_name="completed_at"),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_json_mapping(self.metadata, field_name="result metadata"),
        )

    @classmethod
    def success(
        cls,
        *,
        completed_at: datetime,
        value: T | None = None,
        artifacts: tuple[ArtifactRef, ...] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> Self:
        """Create a successful logical Run result."""
        return cls(
            completed_at=completed_at,
            value=value,
            artifacts=artifacts,
            metadata={} if metadata is None else metadata,
        )

    @classmethod
    def from_failure(
        cls,
        failure: Failure,
        *,
        completed_at: datetime,
        artifacts: tuple[ArtifactRef, ...] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> Self:
        """Create a failed logical Run result from a normalized Failure."""
        return cls(
            completed_at=completed_at,
            failure=failure,
            artifacts=artifacts,
            metadata={} if metadata is None else metadata,
        )

    @property
    def succeeded(self) -> bool:
        return self.failure is None

    @property
    def failed(self) -> bool:
        return self.failure is not None

    def metadata_dict(self) -> dict[str, object]:
        """Return detached metadata suitable for serialization."""
        return plain_json_mapping(self.metadata)


__all__ = ["ArtifactRef", "ExecutionResult", "RunResult"]
