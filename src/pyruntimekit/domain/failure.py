"""Normalized durable Failure domain model."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .enums import FailureCategory, FailureOrigin, FailureScope, FailureSeverity
from .ids import FailureId
from .validation import (
    datetime_to_utc_iso,
    freeze_json_mapping,
    normalize_aware_datetime,
    plain_json_mapping,
    require_text,
)

FAILURE_SCHEMA_VERSION = 1
_FAILURE_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:[._-][A-Z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class FailureCode:
    """Stable machine-readable symbolic failure code."""

    value: str

    def __post_init__(self) -> None:
        normalized = require_text(self.value, field_name="failure code")
        if _FAILURE_CODE_PATTERN.fullmatch(normalized) is None:
            raise ValueError(
                "failure code must use uppercase symbolic segments separated by '.', '_' or '-'"
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class FailureDetails:
    """Structured immutable diagnostic details."""

    values: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "values",
            freeze_json_mapping(self.values, field_name="failure details"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return detached serialization-friendly details."""
        return plain_json_mapping(self.values)


@dataclass(frozen=True, slots=True)
class FailureCauseSummary:
    """Safe non-recursive summary of an underlying local cause."""

    type_name: str
    message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "type_name",
            require_text(self.type_name, field_name="cause type_name"),
        )
        if self.message is not None:
            object.__setattr__(
                self,
                "message",
                require_text(self.message, field_name="cause message"),
            )

    def to_dict(self) -> dict[str, object]:
        """Return the stable serialized cause summary."""
        return {
            "type_name": self.type_name,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True, repr=False)
class Failure:
    """Immutable normalized runtime knowledge about an observed failure."""

    failure_id: FailureId
    code: FailureCode
    category: FailureCategory
    origin: FailureOrigin
    severity: FailureSeverity
    scope: FailureScope
    message: str
    retryable: bool
    recoverable: bool
    occurred_at: datetime
    details: FailureDetails = field(default_factory=FailureDetails)
    cause: FailureCauseSummary | None = None
    traceback_ref: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    schema_version: int = FAILURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.failure_id, FailureId):
            raise TypeError("failure_id must be a FailureId")
        if not isinstance(self.code, FailureCode):
            raise TypeError("code must be a FailureCode")
        if not isinstance(self.category, FailureCategory):
            raise TypeError("category must be a FailureCategory")
        if not isinstance(self.origin, FailureOrigin):
            raise TypeError("origin must be a FailureOrigin")
        if not isinstance(self.severity, FailureSeverity):
            raise TypeError("severity must be a FailureSeverity")
        if not isinstance(self.scope, FailureScope):
            raise TypeError("scope must be a FailureScope")
        if not isinstance(self.retryable, bool):
            raise TypeError("retryable must be a bool")
        if not isinstance(self.recoverable, bool):
            raise TypeError("recoverable must be a bool")
        if not isinstance(self.details, FailureDetails):
            raise TypeError("details must be FailureDetails")
        if self.cause is not None and not isinstance(self.cause, FailureCauseSummary):
            raise TypeError("cause must be FailureCauseSummary or None")
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int):
            raise TypeError("schema_version must be an integer")
        if self.schema_version <= 0:
            raise ValueError("schema_version must be greater than zero")

        object.__setattr__(
            self,
            "message",
            require_text(self.message, field_name="message"),
        )
        object.__setattr__(
            self,
            "occurred_at",
            normalize_aware_datetime(self.occurred_at, field_name="occurred_at"),
        )
        if self.traceback_ref is not None:
            object.__setattr__(
                self,
                "traceback_ref",
                require_text(self.traceback_ref, field_name="traceback_ref"),
            )
        object.__setattr__(
            self,
            "metadata",
            freeze_json_mapping(self.metadata, field_name="failure metadata"),
        )

    @classmethod
    def create(
        cls,
        *,
        code: FailureCode,
        category: FailureCategory,
        origin: FailureOrigin,
        severity: FailureSeverity,
        scope: FailureScope,
        message: str,
        retryable: bool,
        recoverable: bool,
        details: FailureDetails | None = None,
        cause: FailureCauseSummary | None = None,
        traceback_ref: str | None = None,
        metadata: Mapping[str, object] | None = None,
        failure_id: FailureId | None = None,
        occurred_at: datetime | None = None,
    ) -> Failure:
        """Create a normalized Failure with generated identity/time when omitted."""
        return cls(
            failure_id=FailureId.new() if failure_id is None else failure_id,
            code=code,
            category=category,
            origin=origin,
            severity=severity,
            scope=scope,
            message=message,
            retryable=retryable,
            recoverable=recoverable,
            occurred_at=datetime.now(UTC) if occurred_at is None else occurred_at,
            details=FailureDetails() if details is None else details,
            cause=cause,
            traceback_ref=traceback_ref,
            metadata={} if metadata is None else metadata,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the stable serialization-friendly Failure representation."""
        return {
            "schema_version": self.schema_version,
            "failure_id": self.failure_id.value,
            "code": self.code.value,
            "category": self.category.value,
            "origin": self.origin.value,
            "severity": self.severity.value,
            "scope": self.scope.value,
            "message": self.message,
            "retryable": self.retryable,
            "recoverable": self.recoverable,
            "occurred_at": datetime_to_utc_iso(self.occurred_at, field_name="occurred_at"),
            "details": self.details.to_dict(),
            "cause": None if self.cause is None else self.cause.to_dict(),
            "traceback_ref": self.traceback_ref,
            "metadata": plain_json_mapping(self.metadata),
        }

    def __str__(self) -> str:
        return f"{self.code.value} [{self.category.value}/{self.origin.value}]"

    def __repr__(self) -> str:
        return (
            "Failure("
            f"failure_id={self.failure_id!r}, "
            f"code={self.code.value!r}, "
            f"category={self.category.value!r}, "
            f"origin={self.origin.value!r}, "
            f"severity={self.severity.value!r}, "
            f"scope={self.scope.value!r}, "
            f"retryable={self.retryable!r}, "
            f"recoverable={self.recoverable!r}"
            ")"
        )


__all__ = [
    "FAILURE_SCHEMA_VERSION",
    "Failure",
    "FailureCauseSummary",
    "FailureCode",
    "FailureDetails",
]
