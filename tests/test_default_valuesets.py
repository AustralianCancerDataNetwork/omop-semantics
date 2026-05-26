from __future__ import annotations

from omop_semantics.runtime.default_valuesets import runtime


def test_default_valuesets_support_stable_attribute_access() -> None:
    assert runtime.types.disease_episode_types.episode_of_care == 32533
    assert runtime.types.source_types.ehr_defined == 32544


def test_default_valuesets_expose_id_sets_for_downstream_use() -> None:
    episode_types = runtime.types.disease_episode_types

    assert 32533 in episode_types.ids
    assert 32949 in episode_types.ids
    assert "episode_of_care" in episode_types.labels
