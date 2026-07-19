from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

from textual.widgets import TextArea, Tree

from omop_semantics import INSTANCE_DIR
from omop_semantics.runtime import (
    ContextFieldRef,
    DerivationRule,
    OmopSemanticEngine,
    OutputDefinition,
    OutputRowProjection,
    SpecialValuePolicy,
    derive_status,
)
from omop_semantics.runtime.tui.app import OutputDefinitionExplorer


def _engine() -> OmopSemanticEngine:
    return OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[],
    )


def _runtime():
    return _engine().build_output_definition_runtime(
        [_condition_with_status_definition(), _criteria_gate_definition()]
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


def _service_mode_project(runtime):
    def project(definition_name: str, raw: dict[str, Any]):
        grounded: dict[str, Any] = {
            "concept_id": raw["grounded_concept_id"],
        }
        if raw.get("grounded_domain"):
            grounded["domain"] = raw["grounded_domain"]
        bundle = runtime.project(
            definition_name,
            {
                "grounded": grounded,
                "source": dict(raw.get("context", {})),
            },
        )
        return SimpleNamespace(
            status=derive_status(
                has_rows=bool(bundle.rows),
                has_unresolved=bool(bundle.unresolved_fields),
                has_suppressed=bool(bundle.suppressed_rows),
            ),
            rows=[
                SimpleNamespace(row_id=row.row_id, table=row.profile.cdm_table, fields=dict(row.fields))
                for row in bundle.rows
            ],
            suppressed_rows=[
                SimpleNamespace(
                    row_id=row.row_id,
                    reason=row.reason,
                    source_field=row.source_field,
                    source_code=row.source_code,
                )
                for row in bundle.suppressed_rows
            ],
            unresolved_fields=list(bundle.unresolved_fields),
            audit_notes=list(bundle.audit_notes),
            definition_name=bundle.definition_name,
            role=bundle.role,
        )

    return project


def _labels(node) -> list[str]:
    label = getattr(node.label, "plain", str(node.label))
    labels = [label]
    for child in node.children:
        labels.extend(_labels(child))
    return labels


def _child_with_label(node, label: str):
    for child in node.children:
        if child.label.plain == label:
            return child
    raise AssertionError(f"Could not find child node with label {label!r}")


def test_tui_catalogue_has_two_top_level_nodes() -> None:
    async def scenario() -> None:
        runtime = _runtime()
        app = OutputDefinitionExplorer(runtime, project_fn=_service_mode_project(runtime))
        async with app.run_test() as pilot:
            await pilot.pause()
            catalogue = app.query_one("#catalogue", Tree)
            labels = [node.label.plain for node in catalogue.root.children]
            assert labels == [
                "condition_with_status_from_secondary_field",
                "criteria_gate_condition",
            ]

    asyncio.run(scenario())


def test_tui_selection_populates_definition_hint_in_context() -> None:
    async def scenario() -> None:
        runtime = _runtime()
        app = OutputDefinitionExplorer(runtime, project_fn=_service_mode_project(runtime))
        async with app.run_test() as pilot:
            await pilot.pause()
            catalogue = app.query_one("#catalogue", Tree)
            catalogue.select_node(catalogue.root.children[1])
            await pilot.pause()
            payload = json.loads(app.query_one("#context", TextArea).text)
            assert payload["definition_hint"] == "criteria_gate_condition"

    asyncio.run(scenario())


def test_tui_selecting_row_node_does_not_reset_context() -> None:
    async def scenario() -> None:
        runtime = _runtime()
        app = OutputDefinitionExplorer(runtime, project_fn=_service_mode_project(runtime))
        async with app.run_test() as pilot:
            await pilot.pause()
            catalogue = app.query_one("#catalogue", Tree)
            context = app.query_one("#context", TextArea)
            row_node = catalogue.root.children[0].children[0]
            context.load_text('{"edited": "row"}')
            catalogue.select_node(row_node)
            await pilot.pause()
            assert context.text == '{"edited": "row"}'

    asyncio.run(scenario())


def test_tui_selecting_derived_leaf_does_not_reset_context() -> None:
    async def scenario() -> None:
        runtime = _runtime()
        app = OutputDefinitionExplorer(runtime, project_fn=_service_mode_project(runtime))
        async with app.run_test() as pilot:
            await pilot.pause()
            catalogue = app.query_one("#catalogue", Tree)
            context = app.query_one("#context", TextArea)
            row_node = catalogue.root.children[0].children[0]
            derived_node = _child_with_label(
                row_node,
                "=> condition_status_concept_id from source.role_field",
            )
            context.load_text('{"edited": "derived"}')
            catalogue.select_node(derived_node)
            await pilot.pause()
            assert context.text == '{"edited": "derived"}'

    asyncio.run(scenario())


def test_tui_selecting_suppression_leaf_does_not_reset_context() -> None:
    async def scenario() -> None:
        runtime = _runtime()
        app = OutputDefinitionExplorer(runtime, project_fn=_service_mode_project(runtime))
        async with app.run_test() as pilot:
            await pilot.pause()
            catalogue = app.query_one("#catalogue", Tree)
            context = app.query_one("#context", TextArea)
            row_node = catalogue.root.children[1].children[0]
            suppression_node = _child_with_label(row_node, "! suppresses on match")
            context.load_text('{"edited": "suppression"}')
            catalogue.select_node(suppression_node)
            await pilot.pause()
            assert context.text == '{"edited": "suppression"}'

    asyncio.run(scenario())


def test_tui_selecting_different_definition_still_resets_context() -> None:
    async def scenario() -> None:
        runtime = _runtime()
        app = OutputDefinitionExplorer(runtime, project_fn=_service_mode_project(runtime))
        async with app.run_test() as pilot:
            await pilot.pause()
            catalogue = app.query_one("#catalogue", Tree)
            context = app.query_one("#context", TextArea)
            context.load_text('{"edited": "definition"}')
            catalogue.select_node(catalogue.root.children[1])
            await pilot.pause()
            payload = json.loads(context.text)
            assert payload["definition_hint"] == "criteria_gate_condition"

    asyncio.run(scenario())


def test_tui_reselecting_same_definition_does_not_reset_context() -> None:
    async def scenario() -> None:
        runtime = _runtime()
        app = OutputDefinitionExplorer(runtime, project_fn=_service_mode_project(runtime))
        async with app.run_test() as pilot:
            await pilot.pause()
            catalogue = app.query_one("#catalogue", Tree)
            context = app.query_one("#context", TextArea)
            definition_node = catalogue.root.children[0]
            context.load_text('{"edited": "same-definition"}')
            app.on_tree_node_selected(SimpleNamespace(control=catalogue, node=definition_node))
            await pilot.pause()
            assert context.text == '{"edited": "same-definition"}'

    asyncio.run(scenario())


def test_tui_run_kept_projection_renders_expected_fields() -> None:
    async def scenario() -> None:
        runtime = _runtime()
        app = OutputDefinitionExplorer(runtime, project_fn=_service_mode_project(runtime))
        async with app.run_test() as pilot:
            await pilot.pause()
            context = app.query_one("#context", TextArea)
            context.load_text(
                json.dumps(
                    {
                        "grounded_concept_id": 4152280,
                        "grounded_domain": "Condition",
                        "definition_hint": "condition_with_status_from_secondary_field",
                        "context": {"role_field": "1"},
                    },
                    indent=2,
                )
            )
            await pilot.press("ctrl+r")
            await pilot.pause()

            labels = _labels(app.query_one("#result-tree", Tree).root)
            assert "[ok] condition (condition_occurrence)" in labels
            assert "condition_concept_id = 4152280" in labels
            assert "condition_status_concept_id = 32902" in labels

    asyncio.run(scenario())


def test_tui_run_suppressed_projection_renders_reason() -> None:
    async def scenario() -> None:
        runtime = _runtime()
        app = OutputDefinitionExplorer(runtime, project_fn=_service_mode_project(runtime))
        async with app.run_test() as pilot:
            await pilot.pause()
            context = app.query_one("#context", TextArea)
            context.load_text(
                json.dumps(
                    {
                        "grounded_concept_id": 4152280,
                        "grounded_domain": "Condition",
                        "definition_hint": "condition_with_status_from_secondary_field",
                        "context": {"role_field": "3"},
                    },
                    indent=2,
                )
            )
            await pilot.press("ctrl+r")
            await pilot.pause()

            labels = _labels(app.query_one("#result-tree", Tree).root)
            assert "[suppressed] condition" in labels
            assert any("source_code = 3" == label for label in labels)

    asyncio.run(scenario())


def test_tui_invalid_json_shows_inline_error_and_does_not_crash() -> None:
    async def scenario() -> None:
        runtime = _runtime()
        app = OutputDefinitionExplorer(runtime, project_fn=_service_mode_project(runtime))
        async with app.run_test() as pilot:
            await pilot.pause()
            context = app.query_one("#context", TextArea)
            context.load_text("{")
            await pilot.press("ctrl+r")
            await pilot.pause()

            labels = _labels(app.query_one("#result-tree", Tree).root)
            assert any(label.startswith("Invalid JSON:") for label in labels)

    asyncio.run(scenario())


def test_tui_project_exception_shows_inline_error_and_does_not_crash() -> None:
    def raising_project(_definition_name: str, _raw: dict[str, Any]):
        raise KeyError("grounded_concept_id")

    async def scenario() -> None:
        app = OutputDefinitionExplorer(_runtime(), project_fn=raising_project)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()

            labels = _labels(app.query_one("#result-tree", Tree).root)
            assert any("grounded_concept_id" in label for label in labels)

    asyncio.run(scenario())
