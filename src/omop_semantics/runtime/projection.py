from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from omop_semantics.schema.generated_models.omop_semantic_registry import OmopCdmProfile


@dataclass(frozen=True)
class RuntimeProjectionProfile:
    """
    Attribute-based runtime view over an `OmopCdmProfile`.

    This is the structural counterpart to `RuntimeTemplate`: it exposes
    the CDM row-shape information in a stable, ergonomic form for
    downstream execution layers that need to reason about units,
    operators, inline modifiers, or other supported slots.
    """

    name: str
    cdm_table: str
    concept_slot: str
    value_slot: str | None = None
    unit_slot: str | None = None
    operator_slot: str | None = None
    modifier_slot: str | None = None
    extra_concept_slots: tuple[str, ...] = ()
    numeric_slots: tuple[str, ...] = ()
    string_slots: tuple[str, ...] = ()
    reference_slots: tuple[str, ...] = ()

    @classmethod
    def from_profile(cls, profile: OmopCdmProfile) -> "RuntimeProjectionProfile":
        return cls(
            name=profile.name,
            cdm_table=profile.cdm_table,
            concept_slot=profile.concept_slot,
            value_slot=profile.value_slot,
            unit_slot=profile.unit_slot,
            operator_slot=profile.operator_slot,
            modifier_slot=profile.modifier_slot,
            extra_concept_slots=tuple(profile.extra_concept_slots or ()),
            numeric_slots=tuple(profile.numeric_slots or ()),
            string_slots=tuple(profile.string_slots or ()),
            reference_slots=tuple(profile.reference_slots or ()),
        )

    def concept_slots(self) -> tuple[str, ...]:
        slots: list[str] = [self.concept_slot]
        if self.modifier_slot is not None:
            slots.append(self.modifier_slot)
        slots.extend(self.extra_concept_slots)
        if self.unit_slot is not None:
            slots.append(self.unit_slot)
        if self.operator_slot is not None:
            slots.append(self.operator_slot)
        return tuple(slots)

    def all_slots(self) -> tuple[str, ...]:
        slots: list[str] = [self.concept_slot]
        if self.value_slot is not None:
            slots.append(self.value_slot)
        if self.unit_slot is not None:
            slots.append(self.unit_slot)
        if self.operator_slot is not None:
            slots.append(self.operator_slot)
        if self.modifier_slot is not None:
            slots.append(self.modifier_slot)
        slots.extend(self.extra_concept_slots)
        slots.extend(self.numeric_slots)
        slots.extend(self.string_slots)
        slots.extend(self.reference_slots)
        return tuple(slots)

    def allows_slot(self, slot: str) -> bool:
        return slot in self.all_slots()


class ProjectionProfileRuntime:
    """
    Indexed runtime access to compiled CDM projection profiles.

    This keeps the structural profile catalogue available at runtime
    even when execution is not yet using higher-level output definitions.
    """

    def __init__(self, profiles: Mapping[str, OmopCdmProfile]):
        self._profiles = dict(profiles)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._profiles))

    def get(self, name: str) -> RuntimeProjectionProfile:
        return RuntimeProjectionProfile.from_profile(self._profiles[name])

    def by_table(self, cdm_table: str) -> list[RuntimeProjectionProfile]:
        return [
            RuntimeProjectionProfile.from_profile(profile)
            for profile in self._profiles.values()
            if profile.cdm_table == cdm_table
        ]


@dataclass(frozen=True)
class ProjectedOutputRow:
    """
    One projected row produced by a deterministic semantic execution step.
    """

    row_id: str
    profile: RuntimeProjectionProfile
    fields: dict[str, Any]

    def __post_init__(self) -> None:
        unknown_slots = sorted(set(self.fields) - set(self.profile.all_slots()))
        if unknown_slots:
            raise ValueError(
                f"Projected row '{self.row_id}' contains fields not allowed by "
                f"profile '{self.profile.name}': {unknown_slots}"
            )
        if self.profile.concept_slot not in self.fields:
            raise ValueError(
                f"Projected row '{self.row_id}' is missing required concept slot "
                f"'{self.profile.concept_slot}' for profile '{self.profile.name}'"
            )


@dataclass(frozen=True)
class SuppressedRow:
    """
    A row a definition would have produced, dropped deterministically by a
    `DerivationRule` or row-level suppression policy rather than fabricated
    with a missing or null slot value.
    """

    row_id: str
    reason: str
    source_field: str
    source_code: str


@dataclass(frozen=True)
class ProjectedOutputLink:
    """
    Relationship between projected rows.
    """

    source_row: str
    target_row: str
    relationship_type: str
    source_field: str | None = None
    target_field: str | None = None


@dataclass(frozen=True)
class ProjectedOutputBundle:
    """
    Transport-friendly deterministic projection result.
    """

    definition_name: str
    role: str
    rows: list[ProjectedOutputRow]
    links: list[ProjectedOutputLink] = field(default_factory=list)
    constraint_checks: list[dict[str, Any]] = field(default_factory=list)
    unresolved_fields: list[dict[str, Any]] = field(default_factory=list)
    suppressed_rows: list[SuppressedRow] = field(default_factory=list)
    audit_notes: list[str] = field(default_factory=list)

    def row(self, row_id: str) -> ProjectedOutputRow:
        for row in self.rows:
            if row.row_id == row_id:
                return row
        raise KeyError(f"No projected row with id '{row_id}'")

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_name": self.definition_name,
            "role": self.role,
            "rows": [
                {
                    "row_id": row.row_id,
                    "profile": row.profile.name,
                    "cdm_table": row.profile.cdm_table,
                    "fields": dict(row.fields),
                }
                for row in self.rows
            ],
            "links": [
                {
                    "source_row": link.source_row,
                    "target_row": link.target_row,
                    "relationship_type": link.relationship_type,
                    "source_field": link.source_field,
                    "target_field": link.target_field,
                }
                for link in self.links
            ],
            "constraint_checks": [dict(item) for item in self.constraint_checks],
            "unresolved_fields": [dict(item) for item in self.unresolved_fields],
            "suppressed_rows": [
                {
                    "row_id": row.row_id,
                    "reason": row.reason,
                    "source_field": row.source_field,
                    "source_code": row.source_code,
                }
                for row in self.suppressed_rows
            ],
            "audit_notes": list(self.audit_notes),
        }
