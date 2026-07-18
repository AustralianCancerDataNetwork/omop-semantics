from __future__ import annotations

from omop_semantics import INSTANCE_DIR
from omop_semantics.runtime import (
    ContextFieldRef,
    DerivationRule,
    OmopSemanticEngine,
    OutputDefinition,
    OutputLinkRule,
    OutputRowProjection,
    ProjectedOutputBundle,
    ProjectedOutputRow,
    SpecialValuePolicy,
    SuppressedRow,
    bundle_to_html,
    bundle_to_mermaid,
    catalogue_to_html,
    catalogue_to_mermaid,
    describe_definition,
)


def _engine() -> OmopSemanticEngine:
    return OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )


def _criteria_gate_definition() -> OutputDefinition:
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
                special_value_policy=SpecialValuePolicy(
                    source_field=ContextFieldRef("source.raw_value"),
                    allowed_special_values=frozenset({"0"}),
                    suppression_mode="drop",
                ),
            ),
        ),
    )


def _condition_with_status_definition() -> OutputDefinition:
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
        derivation_rules=(
            DerivationRule(
                target_row="condition",
                target_slot="condition_status_concept_id",
                source_field=ContextFieldRef("source.role_field"),
                code_map={"1": 32902, "2": 32908},
                suppress_codes=frozenset({"3"}),
            ),
        ),
    )


def _modified_procedure_definition() -> OutputDefinition:
    return OutputDefinition(
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


def test_bundle_to_mermaid_renders_ok_rows() -> None:
    runtime = _engine().build_output_definition_runtime([_condition_with_status_definition()])
    bundle = runtime.project(
        "condition_with_status_from_secondary_field",
        {"grounded": {"concept_id": 4152280}, "source": {"role_field": "1"}},
    )

    mermaid = bundle_to_mermaid(bundle)

    assert "flowchart TD" in mermaid
    assert "condition[" in mermaid
    assert ":::ok" in mermaid
    assert "condition_concept_id=4152280" in mermaid
    assert "condition_status_concept_id=32902" in mermaid


def test_bundle_to_mermaid_renders_suppressed_rows() -> None:
    runtime = _engine().build_output_definition_runtime([_condition_with_status_definition()])
    bundle = runtime.project(
        "condition_with_status_from_secondary_field",
        {"grounded": {"concept_id": 4152280}, "source": {"role_field": "3"}},
    )

    mermaid = bundle_to_mermaid(bundle)

    assert "suppressed_condition[" in mermaid
    assert ":::suppressed" in mermaid
    assert "source_field=source.role_field" in mermaid
    assert "source_code=3" in mermaid


def test_bundle_to_mermaid_renders_row_level_unresolved_fields() -> None:
    runtime = _engine().build_output_definition_runtime([_condition_with_status_definition()])
    bundle = runtime.project(
        "condition_with_status_from_secondary_field",
        {"grounded": {"concept_id": 4152280}, "source": {}},
    )

    mermaid = bundle_to_mermaid(bundle)

    assert "unresolved_condition[" in mermaid
    assert ":::unresolved" in mermaid
    assert "missing_fields=condition_status_concept_id" in mermaid


def test_bundle_to_mermaid_renders_links() -> None:
    runtime = _engine().build_output_definition_runtime([_modified_procedure_definition()])
    bundle = runtime.project(
        "modified_procedure_demo",
        {
            "procedure": {"concept_id": 1001},
            "modifier": {"concept_id": 2002, "value_concept_id": 3003},
        },
    )

    mermaid = bundle_to_mermaid(bundle)

    assert "modifier -->|modifies| procedure" in mermaid


def test_catalogue_to_mermaid_renders_derivation_rules() -> None:
    runtime = _engine().build_output_definition_runtime([_condition_with_status_definition()])

    mermaid = catalogue_to_mermaid(runtime)

    assert "source.role_field" in mermaid
    assert "&#8658; condition_status_concept_id" in mermaid


def test_catalogue_to_mermaid_renders_special_value_policy_annotations() -> None:
    runtime = _engine().build_output_definition_runtime([_criteria_gate_definition()])

    mermaid = catalogue_to_mermaid(runtime)

    assert "source.raw_value" in mermaid
    assert "suppresses on match" in mermaid


def test_bundle_and_catalogue_html_embed_mermaid_source() -> None:
    runtime = _engine().build_output_definition_runtime(
        [_condition_with_status_definition(), _criteria_gate_definition()]
    )
    bundle = runtime.project(
        "condition_with_status_from_secondary_field",
        {"grounded": {"concept_id": 4152280}, "source": {"role_field": "1"}},
    )

    bundle_html = bundle_to_html(bundle, title="Role = Primary (kept)")
    catalogue_html = catalogue_to_html(runtime)

    assert "<script type=\"module\">" in bundle_html.raw
    assert "https://unpkg.com/mermaid@10.4.0/dist/mermaid.esm.min.mjs" in bundle_html.raw
    assert bundle_to_mermaid(bundle) in bundle_html.raw
    assert "<script type=\"module\">" in catalogue_html.raw
    assert catalogue_to_mermaid(runtime) in catalogue_html.raw


def test_describe_definition_tracks_only_derived_slots() -> None:
    runtime = _engine().build_output_definition_runtime([_condition_with_status_definition()])
    outline = describe_definition(
        runtime.get("condition_with_status_from_secondary_field")
    )

    assert outline.name == "condition_with_status_from_secondary_field"
    assert outline.rows[0].row_id == "condition"
    assert outline.rows[0].derived_slots == (
        ("condition_status_concept_id", "source.role_field"),
    )
    assert outline.rows[0].suppressible is False


def test_bundle_to_mermaid_uses_collision_safe_ids() -> None:
    profile = _engine().projection_profiles.get("condition_simple")
    bundle = ProjectedOutputBundle(
        definition_name="collision_demo",
        role="condition_modifier",
        rows=[
            ProjectedOutputRow(
                row_id="a-b",
                profile=profile,
                fields={"condition_concept_id": 1},
            ),
            ProjectedOutputRow(
                row_id="a_b",
                profile=profile,
                fields={"condition_concept_id": 2},
            ),
        ],
    )

    mermaid = bundle_to_mermaid(bundle)

    assert "a_b[" in mermaid
    assert "a_b_2[" in mermaid


def test_bundle_to_mermaid_escapes_user_supplied_labels() -> None:
    profile = _engine().projection_profiles.get("condition_simple")
    bundle = ProjectedOutputBundle(
        definition_name="escape_demo",
        role="condition_modifier",
        rows=[
            ProjectedOutputRow(
                row_id='condition "<tag>"|1',
                profile=profile,
                fields={"condition_concept_id": '<b>"quoted"|value'},
            )
        ],
        suppressed_rows=[
            SuppressedRow(
                row_id='suppressed "<tag>"|1',
                reason='<script>alert("x")</script>',
                source_field='source|"field"',
                source_code='<0>',
            )
        ],
        audit_notes=['<script>alert("x")</script>'],
    )

    mermaid = bundle_to_mermaid(bundle)
    html = bundle_to_html(bundle)

    assert "&lt;tag&gt;" in mermaid
    assert "&quot;" in mermaid
    assert "&#124;" in mermaid
    assert "<script>alert" not in html.raw
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html.raw
