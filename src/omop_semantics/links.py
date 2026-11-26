"""Registry of OMOP CDM event-field links."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from ruamel.yaml import YAML

from omop_semantics.runtime.default_valuesets import runtime
from omop_semantics.schema.generated_models.omop_links import LinkMechanismCatalogue
from omop_semantics.utils.paths import INSTANCE_DIR


@dataclass(frozen=True)
class LinkMechanism:
    """The CDM table and columns that store an event-field link."""

    name: str
    linking_table: str
    event_id_column: str
    field_concept_column: str


def _load_link_mechanisms(
    path: Path = INSTANCE_DIR / "link_mechanisms.yaml",
) -> Mapping[str, LinkMechanism]:
    """Validate the catalogue and index its mechanisms by name."""
    with path.open(encoding="utf-8") as stream:
        catalogue = LinkMechanismCatalogue.model_validate(YAML(typ="safe").load(stream))

    mechanisms = {
        entry.name: LinkMechanism(
            name=entry.name,
            linking_table=entry.linking_table,
            event_id_column=entry.event_id_column,
            field_concept_column=entry.field_concept_column,
        )
        for entry in catalogue.link_mechanisms
    }
    if len(mechanisms) != len(catalogue.link_mechanisms):
        raise ValueError(f"Duplicate link mechanism names in {path}")

    return MappingProxyType(mechanisms)


LINK_MECHANISMS: Mapping[str, LinkMechanism] = _load_link_mechanisms()
_FIELD_CONCEPT_IDS = MappingProxyType(runtime.modifiers.modifier_fields.exact_mapper())


def field_concept_id(target_table: str) -> int:
    """Return the CDM field concept for the target table's row identifier."""
    label = f"{target_table}_id"
    concept_id = _FIELD_CONCEPT_IDS.get(label)
    if concept_id is None:
        raise ValueError(
            f"Unknown link target table {target_table!r}: {label!r} is not in modifier_fields"
        )
    return concept_id


__all__ = ["LinkMechanism", "LINK_MECHANISMS", "field_concept_id"]
