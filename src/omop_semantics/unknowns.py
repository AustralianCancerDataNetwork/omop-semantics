"""
Canonical fallback concepts for OMOP CDM workflows.

This module defines the standard set of "unknown" and default concepts
used when a mapping cannot be completed confidently. Each entry carries
a reason code describing the failure mode, which is distinct from the
concept ID alone and intentionally not folded into the value-set runtime.

The ``reason`` field is a behavioral policy annotation, not a vocabulary
property — it describes what the caller should communicate about why this
fallback was chosen (e.g. the source was absent vs. the mapping failed).

This is a stable public surface. External consumers should import from
``omop_semantics.unknowns``:

    >>> from omop_semantics.unknowns import UNKNOWN
    >>> UNKNOWN["generic"].concept_id
    4129922
    >>> UNKNOWN["condition"].reason
    'mapping_failed'
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal


UnknownReason = Literal[
    "missing",
    "not_recorded",
    "not_applicable",
    "ambiguous",
    "mapping_failed",
    "default_value",
]


@dataclass(frozen=True)
class UnknownValue:
    """
    A single canonical fallback concept with an attached reason code.

    Attributes
    ----------
    concept_id
        OMOP concept_id of the fallback concept.
    label
        Human-readable label for the concept.
    reason
        Why this fallback is used. Describes the failure mode, not the
        concept itself.
    """

    concept_id: int
    label: str
    reason: UnknownReason | None = None


UNKNOWN: Mapping[str, UnknownValue] = MappingProxyType({
    "generic":             UnknownValue(4129922,  "Unknown",                                        "missing"),
    "gender":              UnknownValue(4214687,  "Gender Unknown",                                 "missing"),
    "condition":           UnknownValue(44790729, "Unknown problem",                                "mapping_failed"),
    "cancer":              UnknownValue(36402660, "Unknown histology of unknown primary site",      "mapping_failed"),
    "grade":               UnknownValue(4264626,  "Grade not determined",                           "not_recorded"),
    "stage":               UnknownValue(36768646, "Cancer Modifier Origin Grade X",                 "not_recorded"),
    "cob":                 UnknownValue(40482029, "Country of birth unknown",                       "missing"),
    "stage_edition":       UnknownValue(1634449,  "8th",                                            "default_value"),
    "therapeutic_regimen": UnknownValue(4207655,  "prescription of therapeutic regimen",            "mapping_failed"),
    "drug_trial":          UnknownValue(4207655,  "clinical drug trial",                            "ambiguous"),
})

__all__ = ["UnknownReason", "UnknownValue", "UNKNOWN"]
