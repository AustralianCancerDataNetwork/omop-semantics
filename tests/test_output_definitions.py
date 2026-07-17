from __future__ import annotations

import pytest

from omop_semantics import INSTANCE_DIR
from omop_semantics.runtime import (
    ContextFieldRef,
    DerivationRule,
    OmopSemanticEngine,
    OutputDefinition,
    OutputLinkRule,
    OutputRowProjection,
    SpecialValuePolicy,
)


def _criteria_gate_definition(**overrides) -> OutputDefinition:
    special_value_policy = overrides.pop(
        "special_value_policy",
        SpecialValuePolicy(
            source_field=ContextFieldRef("source.raw_value"),
            allowed_special_values=frozenset({"0"}),
            suppression_mode="drop",
        ),
    )
    return OutputDefinition(
        name="criteria_gate_condition",
        role="condition_modifier",
        row_projections=(
            OutputRowProjection(
                row_id="condition",
                profile_name="condition_simple",
                field_bindings={
                    "condition_concept_id": ContextFieldRef("grounded.concept_id"),
                },
                special_value_policy=special_value_policy,
            ),
        ),
        **overrides,
    )


def _condition_with_status_definition(**overrides) -> OutputDefinition:
    derivation_rules = overrides.pop(
        "derivation_rules",
        (
            DerivationRule(
                target_row="condition",
                target_slot="condition_status_concept_id",
                source_field=ContextFieldRef("source.role_field"),
                code_map={"1": 32902, "2": 32908},
                suppress_codes=frozenset({"3"}),
            ),
        ),
    )
    return OutputDefinition(
        name="condition_with_status_from_secondary_field",
        role="condition_modifier",
        row_projections=(
            OutputRowProjection(
                row_id="condition",
                profile_name="condition_with_status",
                field_bindings={
                    "condition_concept_id": ContextFieldRef("grounded.concept_id"),
                },
            ),
        ),
        derivation_rules=derivation_rules,
        **overrides,
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


def test_derivation_rule_resolves_slot_from_secondary_source_field() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime([_condition_with_status_definition()])

    bundle = runtime.project(
        "condition_with_status_from_secondary_field",
        {
            "grounded": {"concept_id": 4152280},
            "source": {"role_field": "1"},
        },
    )

    assert len(bundle.rows) == 1
    assert bundle.rows[0].fields == {
        "condition_concept_id": 4152280,
        "condition_status_concept_id": 32902,
    }
    assert bundle.suppressed_rows == []
    assert bundle.unresolved_fields == []


def test_derivation_rule_resolves_secondary_role_used_for_contributing() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime([_condition_with_status_definition()])

    bundle = runtime.project(
        "condition_with_status_from_secondary_field",
        {
            "grounded": {"concept_id": 4152280},
            "source": {"role_field": "2"},
        },
    )

    assert bundle.rows[0].fields["condition_status_concept_id"] == 32908
    assert bundle.suppressed_rows == []


def test_derivation_rule_suppresses_row_on_suppress_code() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime([_condition_with_status_definition()])

    bundle = runtime.project(
        "condition_with_status_from_secondary_field",
        {
            "grounded": {"concept_id": 4152280},
            "source": {"role_field": "3"},
        },
    )

    assert bundle.rows == []
    assert bundle.unresolved_fields == []
    assert len(bundle.suppressed_rows) == 1
    suppressed = bundle.suppressed_rows[0]
    assert suppressed.row_id == "condition"
    assert suppressed.source_field == "source.role_field"
    assert suppressed.source_code == "3"


def test_derivation_rule_reports_unresolved_when_source_field_missing() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime([_condition_with_status_definition()])

    bundle = runtime.project(
        "condition_with_status_from_secondary_field",
        {
            "grounded": {"concept_id": 4152280},
            "source": {},
        },
    )

    assert bundle.rows == []
    assert bundle.suppressed_rows == []
    assert bundle.unresolved_fields == [
        {
            "row_id": "condition",
            "missing_fields": ["condition_status_concept_id"],
            "required": True,
        }
    ]


def test_derivation_rule_uses_default_when_code_not_in_map_or_suppress_list() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    definition = _condition_with_status_definition(
        derivation_rules=(
            DerivationRule(
                target_row="condition",
                target_slot="condition_status_concept_id",
                source_field=ContextFieldRef("source.role_field"),
                code_map={"1": 32902},
                suppress_codes=frozenset({"3"}),
                default=0,
            ),
        ),
    )
    runtime = engine.build_output_definition_runtime([definition])

    bundle = runtime.project(
        "condition_with_status_from_secondary_field",
        {
            "grounded": {"concept_id": 4152280},
            "source": {"role_field": "9"},
        },
    )

    assert bundle.rows[0].fields["condition_status_concept_id"] == 0
    assert bundle.unresolved_fields == []


def test_derivation_rule_validates_target_row_at_compile_time() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    definition = _condition_with_status_definition(
        derivation_rules=(
            DerivationRule(
                target_row="no_such_row",
                target_slot="condition_status_concept_id",
                source_field=ContextFieldRef("source.role_field"),
                code_map={"1": 32902},
            ),
        ),
    )

    with pytest.raises(ValueError, match="unknown target_row 'no_such_row'"):
        engine.build_output_definition_runtime([definition])


def test_derivation_rule_validates_target_slot_at_compile_time() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    definition = _condition_with_status_definition(
        derivation_rules=(
            DerivationRule(
                target_row="condition",
                target_slot="bogus_slot",
                source_field=ContextFieldRef("source.role_field"),
                code_map={"1": 32902},
            ),
        ),
    )

    with pytest.raises(ValueError, match="targets slot 'bogus_slot' not present in profile"):
        engine.build_output_definition_runtime([definition])


def test_special_value_policy_leaves_row_intact_on_the_positive_answer() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime([_criteria_gate_definition()])

    bundle = runtime.project(
        "criteria_gate_condition",
        {
            "grounded": {"concept_id": 4182210},
            "source": {"raw_value": "1"},
        },
    )

    assert len(bundle.rows) == 1
    assert bundle.rows[0].fields == {"condition_concept_id": 4182210}
    assert bundle.suppressed_rows == []


def test_special_value_policy_drops_row_on_the_negative_answer() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime([_criteria_gate_definition()])

    bundle = runtime.project(
        "criteria_gate_condition",
        {
            "grounded": {"concept_id": 4182210},
            "source": {"raw_value": "0"},
        },
    )

    assert bundle.rows == []
    assert bundle.unresolved_fields == []
    assert len(bundle.suppressed_rows) == 1
    suppressed = bundle.suppressed_rows[0]
    assert suppressed.row_id == "condition"
    assert suppressed.source_field == "source.raw_value"
    assert suppressed.source_code == "0"


def test_special_value_policy_ignores_missing_source_field() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    runtime = engine.build_output_definition_runtime([_criteria_gate_definition()])

    bundle = runtime.project(
        "criteria_gate_condition",
        {
            "grounded": {"concept_id": 4182210},
            "source": {},
        },
    )

    assert len(bundle.rows) == 1
    assert bundle.suppressed_rows == []


def test_special_value_policy_fail_mode_raises() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    definition = _criteria_gate_definition(
        special_value_policy=SpecialValuePolicy(
            source_field=ContextFieldRef("source.raw_value"),
            allowed_special_values=frozenset({"9"}),
            suppression_mode="fail",
        ),
    )
    runtime = engine.build_output_definition_runtime([definition])

    with pytest.raises(ValueError, match="configured to fail"):
        runtime.project(
            "criteria_gate_condition",
            {
                "grounded": {"concept_id": 4182210},
                "source": {"raw_value": "9"},
            },
        )


def test_special_value_policy_unimplemented_mode_raises_not_implemented() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    definition = _criteria_gate_definition(
        special_value_policy=SpecialValuePolicy(
            source_field=ContextFieldRef("source.raw_value"),
            allowed_special_values=frozenset({"0"}),
            suppression_mode="keep_as_value",
        ),
    )
    runtime = engine.build_output_definition_runtime([definition])

    with pytest.raises(NotImplementedError, match="keep_as_value"):
        runtime.project(
            "criteria_gate_condition",
            {
                "grounded": {"concept_id": 4182210},
                "source": {"raw_value": "0"},
            },
        )


def test_special_value_policy_validates_suppression_mode_at_compile_time() -> None:
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )
    definition = _criteria_gate_definition(
        special_value_policy=SpecialValuePolicy(
            source_field=ContextFieldRef("source.raw_value"),
            allowed_special_values=frozenset({"0"}),
            suppression_mode="bogus_mode",
        ),
    )

    with pytest.raises(ValueError, match="unrecognized suppression_mode 'bogus_mode'"):
        engine.build_output_definition_runtime([definition])
