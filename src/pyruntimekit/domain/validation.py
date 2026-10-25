"""Shared pure validation helpers for domain value objects."""

from __future__ import annotations

import json
import math
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import cast


def require_text(value: str, *, field_name: str) -> str:
    """Return stripped non-empty text or reject invalid input."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _validate_json_value(value: object, *, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must not contain NaN or infinity")
        return
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        for key, item in mapping.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings")
            if not key.strip():
                raise ValueError(f"{path} keys must not be empty")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        for index, item in enumerate(sequence):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    raise TypeError(f"{path} must contain only JSON-compatible values")


class FrozenJsonMapping(Mapping[str, object]):
    """Defensively immutable mapping backed by canonical JSON."""

    __slots__ = ("_json",)

    def __init__(
        self,
        values: Mapping[str, object] | None = None,
        *,
        field_name: str = "mapping",
    ) -> None:
        source: dict[str, object] = {} if values is None else dict(values)
        _validate_json_value(source, path=field_name)
        self._json = json.dumps(
            source,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def __getitem__(self, key: str) -> object:
        return self.to_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        raw: object = json.loads(self._json)
        return cast(dict[str, object], raw)

    def to_json(self) -> str:
        return self._json


def freeze_json_mapping(
    values: Mapping[str, object] | None = None,
    *,
    field_name: str = "mapping",
) -> FrozenJsonMapping:
    """Create a defensively immutable JSON-compatible mapping."""
    return FrozenJsonMapping(values, field_name=field_name)


def plain_json_mapping(values: Mapping[str, object]) -> dict[str, object]:
    """Return a detached plain mapping suitable for serialization."""
    if isinstance(values, FrozenJsonMapping):
        return values.to_dict()
    return FrozenJsonMapping(values).to_dict()


def normalize_aware_datetime(value: datetime, *, field_name: str) -> datetime:
    """Validate an aware datetime and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def datetime_to_utc_iso(value: datetime, *, field_name: str) -> str:
    """Serialize an aware datetime as an ISO-8601 UTC string."""
    normalized = normalize_aware_datetime(value, field_name=field_name)
    return normalized.isoformat().replace("+00:00", "Z")


def datetime_from_utc_iso(value: str, *, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 datetime") from exc
    return normalize_aware_datetime(parsed, field_name=field_name)


__all__ = [
    "FrozenJsonMapping",
    "datetime_from_utc_iso",
    "datetime_to_utc_iso",
    "freeze_json_mapping",
    "normalize_aware_datetime",
    "plain_json_mapping",
    "require_text",
]
