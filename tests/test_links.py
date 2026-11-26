from pathlib import Path

import pytest
from ruamel.yaml import YAML

from omop_semantics import INSTANCE_DIR
from omop_semantics.links import LINK_MECHANISMS, LinkMechanism, _load_link_mechanisms, field_concept_id
from omop_semantics.runtime.default_valuesets import runtime


def test_link_mechanisms_resolve() -> None:
    assert LINK_MECHANISMS == {
        "measurement": LinkMechanism(
            "measurement", "measurement", "measurement_event_id", "meas_event_field_concept_id"
        ),
        "observation": LinkMechanism(
            "observation", "observation", "observation_event_id", "obs_event_field_concept_id"
        ),
        "episode_event": LinkMechanism(
            "episode_event", "episode_event", "event_id", "episode_event_field_concept_id"
        ),
    }


def test_link_mechanisms_reject_duplicate_names(tmp_path: Path) -> None:
    yaml = YAML(typ="safe")
    with (INSTANCE_DIR / "link_mechanisms.yaml").open(encoding="utf-8") as stream:
        catalogue = yaml.load(stream)
    entries = catalogue["link_mechanisms"]
    entries.append(entries[0].copy())

    path = tmp_path / "link_mechanisms.yaml"
    with path.open("w", encoding="utf-8") as stream:
        yaml.dump(catalogue, stream)

    with pytest.raises(ValueError, match="Duplicate link mechanism names in .*link_mechanisms.yaml"):
        _load_link_mechanisms(path)


def test_modifier_fields_match_cdm_5_4_2() -> None:
    fixture = Path(__file__).with_name("fixtures") / "cdm_5_4_2_link_concepts.yaml"
    with fixture.open(encoding="utf-8") as stream:
        expected = YAML(typ="safe").load(stream)

    assert runtime.modifiers.modifier_fields.exact_mapper() == expected["modifier_fields"]
    for label, concept_id in expected["modifier_fields"].items():
        assert field_concept_id(label.removesuffix("_id")) == concept_id
    assert runtime.modifiers.modifier_tables.episode == expected["episode_table"]


def test_field_concept_id_rejects_unknown_table() -> None:
    with pytest.raises(ValueError, match="Unknown link target table 'invented_table'"):
        field_concept_id("invented_table")
