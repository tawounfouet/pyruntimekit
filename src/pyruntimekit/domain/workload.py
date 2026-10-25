"""Backend-agnostic Workload domain model."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from .enums import IsolationLevel, Priority
from .ids import WorkloadId
from .validation import freeze_json_mapping, plain_json_mapping, require_text


@dataclass(frozen=True, slots=True)
class ResourceHints:
    """Declarative hints used later by placement/executor selection policies."""

    cpu_bound: bool = False
    io_bound: bool = False
    memory_mb: int | None = None
    gpu_required: bool = False
    isolation: IsolationLevel = IsolationLevel.NONE
    priority: Priority = Priority.NORMAL

    def __post_init__(self) -> None:
        if self.memory_mb is not None:
            if isinstance(self.memory_mb, bool) or not isinstance(self.memory_mb, int):
                raise TypeError("memory_mb must be an integer or None")
            if self.memory_mb <= 0:
                raise ValueError("memory_mb must be greater than zero")


@dataclass(frozen=True, slots=True)
class WorkloadDescriptor:
    """Serializable description used to locate or reconstruct a Workload."""

    kind: str
    reference: str
    parameters: Mapping[str, object] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", require_text(self.kind, field_name="kind"))
        object.__setattr__(
            self,
            "reference",
            require_text(self.reference, field_name="reference"),
        )
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int):
            raise TypeError("schema_version must be an integer")
        if self.schema_version <= 0:
            raise ValueError("schema_version must be greater than zero")
        object.__setattr__(
            self,
            "parameters",
            freeze_json_mapping(self.parameters, field_name="parameters"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a detached serialization-friendly representation."""
        return {
            "kind": self.kind,
            "reference": self.reference,
            "parameters": plain_json_mapping(self.parameters),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class WorkloadRef:
    """Stable reconstructible reference to a Workload definition."""

    workload_id: WorkloadId
    descriptor: WorkloadDescriptor

    def to_string(self) -> str:
        """Return the canonical serialized reference."""
        return json.dumps(
            {
                "descriptor": self.descriptor.to_dict(),
                "workload_id": self.workload_id.value,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def from_string(cls, value: str) -> WorkloadRef:
        """Reconstruct a WorkloadRef from its canonical serialized form."""
        if not isinstance(value, str):
            raise TypeError("workload reference must be a string")
        try:
            raw: object = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("workload reference must be valid JSON") from exc
        if not isinstance(raw, dict):
            raise ValueError("workload reference must encode an object")

        payload = cast(dict[str, object], raw)
        workload_id_value = payload.get("workload_id")
        descriptor_value = payload.get("descriptor")
        if not isinstance(workload_id_value, str):
            raise ValueError("workload reference must contain a string workload_id")
        if not isinstance(descriptor_value, dict):
            raise ValueError("workload reference must contain a descriptor object")

        descriptor_payload = cast(dict[str, object], descriptor_value)
        kind = descriptor_payload.get("kind")
        reference = descriptor_payload.get("reference")
        parameters = descriptor_payload.get("parameters", {})
        schema_version = descriptor_payload.get("schema_version")

        if not isinstance(kind, str) or not isinstance(reference, str):
            raise ValueError("descriptor kind and reference must be strings")
        if not isinstance(parameters, dict):
            raise ValueError("descriptor parameters must be an object")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise ValueError("descriptor schema_version must be an integer")

        descriptor = WorkloadDescriptor(
            kind=kind,
            reference=reference,
            parameters=cast(dict[str, object], parameters),
            schema_version=schema_version,
        )
        return cls(
            workload_id=WorkloadId.from_str(workload_id_value),
            descriptor=descriptor,
        )

    def __str__(self) -> str:
        return self.to_string()


@dataclass(frozen=True, slots=True)
class Workload:
    """Immutable logical executable unit submitted to the Runtime."""

    workload_id: WorkloadId
    descriptor: WorkloadDescriptor
    metadata: Mapping[str, object] = field(default_factory=dict)
    resource_hints: ResourceHints = field(default_factory=ResourceHints)
    policy_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metadata",
            freeze_json_mapping(self.metadata, field_name="metadata"),
        )
        normalized_policy_refs = tuple(
            require_text(policy_ref, field_name="policy_ref") for policy_ref in self.policy_refs
        )
        object.__setattr__(self, "policy_refs", normalized_policy_refs)

    @property
    def kind(self) -> str:
        return self.descriptor.kind

    @property
    def parameters(self) -> Mapping[str, object]:
        return self.descriptor.parameters

    @property
    def ref(self) -> WorkloadRef:
        return WorkloadRef(self.workload_id, self.descriptor)

    def metadata_dict(self) -> dict[str, object]:
        """Return detached metadata suitable for serialization."""
        return plain_json_mapping(self.metadata)


__all__ = ["ResourceHints", "Workload", "WorkloadDescriptor", "WorkloadRef"]
