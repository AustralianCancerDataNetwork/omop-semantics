"""Behavioural fallback concepts loaded from the unknowns registry.

The catalogue lives in ``schema/instances/unknowns.yaml`` and is validated
against the generated ``UnknownCatalogue`` model. It stays separate from the
value-set runtime because fallback reasons describe application behavior, not
membership in an OMOP value set.

Import from ``omop_semantics.unknowns``::

    from omop_semantics.unknowns import UNKNOWN

    UNKNOWN["generic"].concept_id
    UNKNOWN["generic"].reason
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from ruamel.yaml import YAML

from omop_semantics.schema.generated_models.omop_unknowns import (
    UnknownCatalogue,
    UnknownReason,
)
from omop_semantics.utils.paths import INSTANCE_DIR


@dataclass(frozen=True)
class UnknownValue:
    """A fallback concept and the reason it is selected."""

    concept_id: int
    label: str
    reason: UnknownReason


def _load_unknowns(path: Path = INSTANCE_DIR / "unknowns.yaml") -> Mapping[str, UnknownValue]:
    """Validate a catalogue file and return its immutable key-to-value mapping."""
    with path.open(encoding="utf-8") as stream:
        catalogue = UnknownCatalogue.model_validate(YAML(typ="safe").load(stream))

    values: dict[str, UnknownValue] = {}
    for entry in catalogue.unknowns:
        label = entry.label
        if label in values:
            raise ValueError(f"Duplicate unknown label: {label!r}")
        values[label] = UnknownValue(
            concept_id=entry.concept_id,
            label=label,
            reason=UnknownReason(entry.reason),
        )

    return MappingProxyType(values)


UNKNOWN: Mapping[str, UnknownValue] = _load_unknowns()

__all__ = ["UnknownReason", "UnknownValue", "UNKNOWN"]
