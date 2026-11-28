"""Shared CDM profiles and deterministic row fragments."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

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
    event_date_slot: str | None = None
    visit_slot: str | None = None
    care_site_slot: str | None = None

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
            event_date_slot=profile.event_date_slot,
            visit_slot=profile.visit_slot,
            care_site_slot=profile.care_site_slot,
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
        slots.extend(
            slot
            for slot in (self.event_date_slot, self.visit_slot, self.care_site_slot)
            if slot is not None
        )
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
    fields: Mapping[str, Any]
    value_rank: int | None = None

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
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))
