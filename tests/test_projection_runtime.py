from __future__ import annotations

import pytest

from omop_semantics import INSTANCE_DIR
from omop_semantics.runtime import (
    OmopSemanticEngine,
    ProjectedOutputBundle,
    ProjectedOutputLink,
    ProjectedOutputRow,
    SuppressedRow,
)


def test_projection_profile_runtime_exposes_extended_profile_slots() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )

    assert engine.projection_profiles is not None

    profile = engine.projection_profiles.get("measurement_numeric_with_operator")
    assert profile.cdm_table == "measurement"
    assert profile.concept_slot == "measurement_concept_id"
    assert profile.value_slot == "value_as_number"
    assert profile.unit_slot == "unit_concept_id"
    assert profile.operator_slot == "operator_concept_id"
    assert profile.allows_slot("measurement_concept_id")
    assert profile.allows_slot("value_as_number")
    assert profile.allows_slot("unit_concept_id")
    assert profile.allows_slot("operator_concept_id")
    assert not profile.allows_slot("not_a_slot")


def test_runtime_template_exposes_projection_profile() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )

    tpl = engine.registry_runtime.get_runtime("Language spoken")
    profile = tpl.projection_profile

    assert profile.name == "observation_coded"
    assert profile.cdm_table == "observation"
    assert profile.concept_slot == "observation_concept_id"
    assert profile.value_slot == "value_as_concept_id"


def test_projected_output_row_validates_profile_slots() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )

    profile = engine.projection_profiles.get("measurement_numeric_with_operator")
    row = ProjectedOutputRow(
        row_id="measurement",
        profile=profile,
        fields={
            "measurement_concept_id": 123,
            "value_as_number": 4.2,
            "unit_concept_id": 9448,
            "operator_concept_id": 4171755,
        },
    )

    assert row.fields["value_as_number"] == 4.2


def test_projected_output_row_rejects_unknown_slots() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )

    profile = engine.projection_profiles.get("measurement_numeric_with_unit")
    with pytest.raises(ValueError, match="not allowed by profile"):
        ProjectedOutputRow(
            row_id="measurement",
            profile=profile,
            fields={
                "measurement_concept_id": 123,
                "value_as_number": 4.2,
                "bogus_field": 99,
            },
        )


def test_projected_output_bundle_serializes_rows_and_links() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )

    procedure_profile = engine.projection_profiles.get("procedure_with_inline_modifier")
    row = ProjectedOutputRow(
        row_id="procedure",
        profile=procedure_profile,
        fields={
            "procedure_concept_id": 1001,
            "modifier_concept_id": 2002,
        },
    )
    link = ProjectedOutputLink(
        source_row="procedure",
        target_row="procedure",
        relationship_type="self_modifier",
        source_field="modifier_concept_id",
        target_field="procedure_concept_id",
    )
    bundle = ProjectedOutputBundle(
        definition_name="inline_modifier_demo",
        role="procedure_modifier",
        rows=[row],
        links=[link],
        constraint_checks=[{"kind": "unit", "status": "not_applicable"}],
        audit_notes=["demo bundle"],
    )

    payload = bundle.to_dict()

    assert payload["definition_name"] == "inline_modifier_demo"
    assert payload["rows"][0]["profile"] == "procedure_with_inline_modifier"
    assert payload["links"][0]["relationship_type"] == "self_modifier"
    assert payload["constraint_checks"][0]["status"] == "not_applicable"
    assert payload["suppressed_rows"] == []


def test_projected_output_bundle_serializes_suppressed_rows() -> None:
    bundle = ProjectedOutputBundle(
        definition_name="condition_with_status_from_secondary_field",
        role="condition_modifier",
        rows=[],
        suppressed_rows=[
            SuppressedRow(
                row_id="condition",
                reason="derivation rule for 'condition_status_concept_id' matched a suppress code",
                source_field="source.role_field",
                source_code="3",
            )
        ],
    )

    payload = bundle.to_dict()

    assert payload["rows"] == []
    assert payload["suppressed_rows"] == [
        {
            "row_id": "condition",
            "reason": (
                "derivation rule for 'condition_status_concept_id' matched a suppress code"
            ),
            "source_field": "source.role_field",
            "source_code": "3",
        }
    ]
