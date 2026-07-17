from __future__ import annotations

import pytest

from omop_semantics import INSTANCE_DIR
from omop_semantics.runtime import (
    ContextFieldRef,
    OmopSemanticEngine,
    OutputDefinition,
    OutputLinkRule,
    OutputRowProjection,
)


def test_output_definition_runtime_projects_rows_from_context() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime(
        [
            OutputDefinition(
                name="numeric_measurement",
                role="measurement",
                template_names=("Country of birth",),
                row_projections=(
                    OutputRowProjection(
                        row_id="measurement",
                        profile_name="measurement_numeric_with_operator",
                        field_bindings={
                            "measurement_concept_id": ContextFieldRef("grounded.concept_id"),
                            "value_as_number": ContextFieldRef("source.numeric_value"),
                            "unit_concept_id": ContextFieldRef("source.unit_concept_id"),
                            "operator_concept_id": ContextFieldRef("source.operator_concept_id"),
                        },
                    ),
                ),
                notes=("numeric measurement demo",),
            )
        ]
    )

    bundle = runtime.project(
        "numeric_measurement",
        {
            "grounded": {"concept_id": 12345},
            "source": {
                "numeric_value": 6.2,
                "unit_concept_id": 8840,
                "operator_concept_id": 4171755,
            },
        },
    )

    assert bundle.definition_name == "numeric_measurement"
    assert bundle.role == "measurement"
    assert bundle.audit_notes == ["numeric measurement demo"]
    assert len(bundle.rows) == 1
    assert bundle.rows[0].fields["measurement_concept_id"] == 12345
    assert bundle.rows[0].fields["value_as_number"] == 6.2
    assert bundle.unresolved_fields == []


def test_output_definition_runtime_projects_links_between_rows() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime(
        [
            OutputDefinition(
                name="modified_procedure_demo",
                role="procedure_modifier",
                row_projections=(
                    OutputRowProjection(
                        row_id="procedure",
                        profile_name="procedure_simple",
                        field_bindings={
                            "procedure_concept_id": ContextFieldRef("procedure.concept_id"),
                        },
                    ),
                    OutputRowProjection(
                        row_id="modifier",
                        profile_name="observation_coded",
                        field_bindings={
                            "observation_concept_id": ContextFieldRef("modifier.concept_id"),
                            "value_as_concept_id": ContextFieldRef("modifier.value_concept_id"),
                        },
                    ),
                ),
                link_rules=(
                    OutputLinkRule(
                        source_row="modifier",
                        target_row="procedure",
                        relationship_type="modifies",
                    ),
                ),
            )
        ]
    )

    bundle = runtime.project(
        "modified_procedure_demo",
        {
            "procedure": {"concept_id": 1001},
            "modifier": {"concept_id": 2002, "value_concept_id": 3003},
        },
    )

    assert len(bundle.rows) == 2
    assert len(bundle.links) == 1
    assert bundle.links[0].relationship_type == "modifies"


def test_output_definition_runtime_reports_unresolved_required_fields() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime(
        [
            OutputDefinition(
                name="smoking_pack_years",
                role="behavioral_exposure",
                row_projections=(
                    OutputRowProjection(
                        row_id="pack_years",
                        profile_name="measurement_numeric_with_unit",
                        field_bindings={
                            "measurement_concept_id": ContextFieldRef("grounded.concept_id"),
                            "value_as_number": ContextFieldRef("source.pack_years"),
                            "unit_concept_id": ContextFieldRef("source.unit_concept_id"),
                        },
                    ),
                ),
            )
        ]
    )

    bundle = runtime.project(
        "smoking_pack_years",
        {
            "grounded": {"concept_id": 111},
            "source": {"pack_years": 40.0},
        },
    )

    assert bundle.rows == []
    assert bundle.unresolved_fields == [
        {
            "row_id": "pack_years",
            "missing_fields": ["unit_concept_id"],
            "required": True,
        }
    ]


def test_output_definition_runtime_validates_slot_names_at_compile_time() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )

    with pytest.raises(ValueError, match="uses slots not present in profile"):
        engine.build_output_definition_runtime(
            [
                OutputDefinition(
                    name="bad_definition",
                    role="measurement",
                    row_projections=(
                        OutputRowProjection(
                            row_id="measurement",
                            profile_name="measurement_numeric_with_unit",
                            field_bindings={
                                "measurement_concept_id": 123,
                                "bogus_field": 999,
                            },
                        ),
                    ),
                )
            ]
        )


def test_output_definition_runtime_project_for_template_requires_unique_match() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime(
        [
            OutputDefinition(
                name="a",
                role="demographic",
                template_names=("Language spoken",),
                row_projections=(
                    OutputRowProjection(
                        row_id="obs",
                        profile_name="observation_coded",
                        field_bindings={
                            "observation_concept_id": ContextFieldRef("grounded.concept_id"),
                            "value_as_concept_id": ContextFieldRef("source.value_concept_id"),
                        },
                    ),
                ),
            ),
            OutputDefinition(
                name="b",
                role="demographic",
                template_names=("Language spoken",),
                row_projections=(
                    OutputRowProjection(
                        row_id="obs",
                        profile_name="observation_coded",
                        field_bindings={
                            "observation_concept_id": ContextFieldRef("grounded.concept_id"),
                            "value_as_concept_id": ContextFieldRef("source.value_concept_id"),
                        },
                    ),
                ),
            ),
        ]
    )

    with pytest.raises(ValueError, match="Multiple output definitions match template"):
        runtime.project_for_template(
            "Language spoken",
            {
                "grounded": {"concept_id": 4052785},
                "source": {"value_concept_id": 4182347},
            },
        )
