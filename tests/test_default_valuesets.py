from __future__ import annotations

import warnings

import pytest

from omop_semantics.runtime.default_valuesets import enumerators, runtime
from omop_semantics.runtime.value_sets import (
    compile_valuesets,
    index_semantic_units,
    interpolate_valuesets,
)


def test_default_valuesets_support_stable_attribute_access() -> None:
    assert runtime.types.disease_episode_types.episode_of_care == 32533
    assert runtime.types.source_types.ehr_defined == 32544


def test_default_valuesets_expose_id_sets_for_downstream_use() -> None:
    episode_types = runtime.types.disease_episode_types

    assert 32533 in episode_types.ids
    assert 32949 in episode_types.ids
    assert "episode_of_care" in episode_types.labels


def test_cancer_procedure_groups_expose_governed_modality_anchors() -> None:
    procedure_types = runtime.cancer_procedures.cancer_procedure_types
    radiotherapy = runtime.cancer_procedures.radiotherapy
    surgery = runtime.cancer_procedures.cancer_indicating_surgery
    diagnostic = runtime.cancer_procedures.diagnostic_staging_procedure

    assert procedure_types.surgical_procedure == 4301351
    assert procedure_types.rt_procedure == 1242725
    assert procedure_types.rt_externalbeam == 4141448
    assert procedure_types.rt_brachytherapy == 40317890
    assert radiotherapy.parent_ids == {1242725, 4141448, 40317890}

    assert surgery.parent_mapper() == {
        "lung_excision": 4000882,
        "gi_tract_excision": 4041977,
        "large_intestine_excision": 4029565,
        "kidney_excision": 4027426,
        "urinary_bladder_excision": 4029571,
        "prostate_operation": 4250917,
        "breast_operation": 4194253,
        "liver_operation": 4171687,
        "endocrine_system_excision": 4027422,
        "lymph_node_excision": 4238646,
    }
    assert surgery.exact_mapper() == {"lobectomy": 4054047}
    assert surgery.exact_ids == {4054047}
    assert surgery.lobectomy == 4054047
    assert diagnostic.parent_ids == {4228202}
    assert diagnostic.exact_ids == {4120443}
    assert diagnostic.excisional_biopsy == 4228202
    assert diagnostic.bone_marrow_sampling == 4120443

    surgery_parents = (
        runtime.cancer_procedures.cancer_indicating_surgery_parent_concepts
    )
    assert surgery_parents.parent_ids == surgery.parent_ids

    diagnostic_parents = (
        runtime.cancer_procedures.diagnostic_staging_procedure_parent_concepts
    )
    assert diagnostic_parents.parent_ids == diagnostic.parent_ids

    with pytest.raises(AttributeError):
        runtime.cancer_procedures.cancer_indicating_surgery_point_concepts
    with pytest.raises(AttributeError):
        runtime.cancer_procedures.diagnostic_staging_procedure_point_concepts

    surgery_html = surgery._repr_html_()
    assert "Group (descendants)" in surgery_html
    assert "Enum (exact)" in surgery_html
    assert "lung_excision" in surgery_html
    assert "lobectomy" in surgery_html
    assert "Cancer-directed surgery" in surgery_html


def test_group_ids_are_deprecated_but_enum_ids_remain_supported() -> None:
    surgery = runtime.cancer_procedures.cancer_indicating_surgery
    surgery_group = surgery.groups["cancer_indicating_surgery_parent_concepts"]

    with pytest.warns(DeprecationWarning, match="use parent_ids"):
        assert surgery_group.ids == surgery.parent_ids

    with pytest.warns(DeprecationWarning, match="group-backed units"):
        assert surgery.ids == surgery.parent_ids | surgery.exact_ids

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert 32533 in runtime.types.disease_episode_types.ids
    assert not [warning for warning in caught if warning.category is DeprecationWarning]


def test_composite_semantic_units_reject_ambiguous_group_composition() -> None:
    semantic_index = index_semantic_units(enumerators)
    raw = {
        "valuesets": [
            {
                "name": "invalid",
                "semantic_units": [
                    {
                        "name": "too_many_groups",
                        "named_groups": ["t_stage_concepts", "n_stage_concepts"],
                    }
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="at most one group"):
        interpolate_valuesets(raw, semantic_index)


def test_composite_semantic_units_validate_typed_references() -> None:
    semantic_index = index_semantic_units(enumerators)
    raw = {
        "valuesets": [
            {
                "name": "invalid",
                "semantic_units": [
                    {
                        "name": "wrong_type",
                        "named_enumerators": ["t_stage_concepts"],
                    }
                ],
            }
        ]
    }

    with pytest.raises(TypeError, match="under 'named_enumerators'"):
        interpolate_valuesets(raw, semantic_index)


def test_composite_semantic_units_reject_flattened_label_collisions() -> None:
    semantic_index = index_semantic_units(enumerators)
    raw = {
        "valuesets": [
            {
                "name": "invalid",
                "semantic_units": [
                    {
                        "name": "duplicate_labels",
                        "named_enumerators": [
                            "cancer_consult_types",
                            "encounter_provider_specialty",
                        ],
                    }
                ],
            }
        ]
    }

    definitions = interpolate_valuesets(raw, semantic_index)
    with pytest.raises(ValueError, match="exposes label 'medonc'"):
        compile_valuesets(definitions)


def test_sact_drug_classification_exposes_inclusion_and_exclusion_anchors() -> None:
    sact = runtime.sact.sact_drug_classification

    assert sact.atc_antineoplastic_and_immunomodulating == 21601386
    assert sact.hemonc_supportive_medication == 35807271
    assert sact.parent_ids == {21601386}
    assert sact.excluded_parent_ids == {35807271}
    assert sact.excluded_parent_mapper() == {
        "hemonc_supportive_medication": 35807271
    }
