from __future__ import annotations

from omop_semantics import INSTANCE_DIR, SCHEMA_DIR
from omop_semantics.runtime import OmopSemanticEngine


def test_semantic_engine_loads_builtin_templates_and_profiles() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[
            INSTANCE_DIR / "demographic.yaml",
        ],
        profile_paths=[
            INSTANCE_DIR / "profile_groups.yaml",
            SCHEMA_DIR / "profiles" / "omop_staging.yaml",
            SCHEMA_DIR / "profiles" / "omop_modifiers.yaml",
            SCHEMA_DIR / "profiles" / "omop_episodes.yaml",
        ],
    )

    tpl = engine.registry_runtime.get_runtime("Country of birth")

    assert tpl.role == "demographic"
    assert tpl.cdm_profile.name == "observation_simple"
    assert tpl.cdm_profile.cdm_table == "observation"
    assert tpl.entity_concept_ids == {4155450}
    assert tpl.value_concept_ids is None


def test_semantic_engine_exposes_profile_groups_and_value_scopes() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[
            INSTANCE_DIR / "demographic.yaml",
        ],
        profile_paths=[
            INSTANCE_DIR / "profile_groups.yaml",
        ],
    )

    assert engine.profile_runtime is not None

    groups = engine.profile_runtime.list_groups()
    assert "ObservationProfiles" in groups
    assert groups["ObservationProfiles"]["members"] == [
        "observation_simple",
        "observation_coded",
        "observation_string",
    ]

    language_spoken = engine.registry_runtime.get_runtime("Language spoken")
    assert language_spoken.cdm_profile.name == "observation_coded"
    assert language_spoken.value_concept_ids == {4182347}
