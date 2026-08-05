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


def test_cancer_procedure_groups_expose_governed_modality_anchors() -> None:
    procedure_types = runtime.cancer_procedures.cancer_procedure_types
    surgery_parents = runtime.cancer_procedures.cancer_indicating_surgery_parent_concepts
    surgery_points = runtime.cancer_procedures.cancer_indicating_surgery_point_concepts
    diagnostic_parents = runtime.cancer_procedures.diagnostic_staging_procedure_parent_concepts
    diagnostic_points = runtime.cancer_procedures.diagnostic_staging_procedure_point_concepts

    assert procedure_types.surgical_procedure == 4301351
    assert procedure_types.rt_procedure == 1242725
    assert procedure_types.rt_externalbeam == 4141448
    assert procedure_types.rt_brachytherapy == 40317890

    assert surgery_parents.mapper() == {
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
    assert surgery_points.lobectomy == 4054047
    assert diagnostic_parents.excisional_biopsy == 4228202
    assert diagnostic_points.bone_marrow_sampling == 4120443


def test_sact_drug_classification_exposes_inclusion_and_exclusion_anchors() -> None:
    sact = runtime.sact.sact_drug_classification

    assert sact.atc_antineoplastic_and_immunomodulating == 21601386
    assert sact.hemonc_supportive_medication == 35807271
    assert sact.ids == {21601386}
    assert sact.excluded_ids == {35807271}
    assert sact.excluded_mapper() == {"hemonc_supportive_medication": 35807271}
