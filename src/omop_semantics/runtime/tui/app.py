from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static, TextArea, Tree

from omop_semantics.runtime.output_definitions import OutputDefinitionRuntime
from omop_semantics.runtime.viz import DefinitionOutline, derive_status, describe_definition

from .widgets import ProjectionViewData, populate_result_tree, render_summary

ProjectCallable = Callable[[str, Mapping[str, Any]], Any]

_DOMAIN_BY_TABLE = {
    "condition_occurrence": "Condition",
    "observation": "Observation",
    "procedure_occurrence": "Procedure",
    "measurement": "Measurement",
    "drug_exposure": "Drug",
    "device_exposure": "Device",
    "death": "Death",
    "specimen": "Specimen",
    "episode": "Episode",
    "episode_event": "Episode",
    "visit_occurrence": "Visit",
}


@dataclass(frozen=True)
class CatalogueNodeData:
    definition_name: str
    kind: str


class OutputDefinitionExplorer(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        layout: vertical;
        height: 1fr;
    }

    #top {
        height: 2fr;
    }

    #catalogue-panel, #context-panel, #result-panel {
        border: round $accent;
        padding: 0 1;
    }

    #catalogue-panel, #context-panel {
        width: 1fr;
    }

    #result-panel {
        height: 1fr;
    }

    .panel-title {
        margin-bottom: 1;
        text-style: bold;
    }

    Tree, TextArea {
        height: 1fr;
    }

    #run {
        margin-top: 1;
        width: 100%;
    }

    #result-summary {
        height: auto;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+r", "run_projection", "Run", priority=True),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        runtime: OutputDefinitionRuntime,
        project_fn: ProjectCallable | None = None,
    ) -> None:
        super().__init__()
        self._runtime = runtime
        self._service_mode = project_fn is not None
        self._project_fn: ProjectCallable = project_fn or runtime.project
        self._selected_definition: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="body"):
            with Horizontal(id="top"):
                with Vertical(id="catalogue-panel"):
                    yield Static("Catalogue", classes="panel-title")
                    yield Tree("Output definitions", id="catalogue")
                with Vertical(id="context-panel"):
                    yield Static("Context (editable JSON)", classes="panel-title")
                    yield TextArea(id="context")
                    yield Button("Run (ctrl+r)", id="run", variant="primary")
            with Vertical(id="result-panel"):
                yield Static("Result", classes="panel-title")
                yield Static("Select a definition to begin.", id="result-summary")
                yield Tree("Projection result", id="result-tree")
        yield Footer()

    def on_mount(self) -> None:
        catalogue = self.query_one("#catalogue", Tree)
        catalogue.show_root = False
        catalogue.root.expand()
        self._populate_catalogue(catalogue)

        result_tree = self.query_one("#result-tree", Tree)
        result_tree.show_root = False
        result_tree.root.expand()

        context = self.query_one("#context", TextArea)
        if not self._runtime.names():
            context.load_text("{}")
            self.query_one("#result-summary", Static).update("No definitions loaded.")
            return

        first = catalogue.root.children[0]
        catalogue.select_node(first)
        self._select_definition(first.data.definition_name if isinstance(first.data, CatalogueNodeData) else None)

    def on_tree_node_selected(self, event: Tree.NodeSelected[CatalogueNodeData]) -> None:
        if event.control.id != "catalogue":
            return
        data = event.node.data
        if not isinstance(data, CatalogueNodeData) or data.kind != "definition":
            return
        if data.definition_name == self._selected_definition:
            return
        self._select_definition(data.definition_name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            self.action_run_projection()

    def action_run_projection(self) -> None:
        if self._selected_definition is None:
            self._show_result(
                ProjectionViewData(
                    status="error",
                    message="Select a definition before running a projection.",
                )
            )
            return

        context_area = self.query_one("#context", TextArea)
        try:
            payload = json.loads(context_area.text)
        except json.JSONDecodeError as exc:
            self._show_result(
                ProjectionViewData(
                    status="error",
                    message=f"Invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}",
                )
            )
            return

        try:
            raw_result = self._project_fn(self._selected_definition, payload)
        except Exception as exc:
            self._show_result(
                ProjectionViewData(
                    status="error",
                    definition_name=self._selected_definition,
                    message=str(exc),
                )
            )
            return

        if self._service_mode:
            view = _extract_service_view(raw_result)
        else:
            view = _extract_runtime_view(raw_result)
        self._show_result(view)

    def _populate_catalogue(self, tree: Tree[CatalogueNodeData]) -> None:
        tree.clear()
        tree.root.expand()
        for definition_name in self._runtime.names():
            outline = describe_definition(self._runtime.get(definition_name))
            definition_node = tree.root.add(
                Text(outline.name),
                data=CatalogueNodeData(definition_name=outline.name, kind="definition"),
                expand=True,
            )
            self._add_outline_rows(definition_node, outline)

    def _add_outline_rows(self, definition_node: Any, outline: DefinitionOutline) -> None:
        for row in outline.rows:
            row_node = definition_node.add(
                Text(f"{row.row_id} ({row.cdm_table} / {row.profile_name})"),
                data=CatalogueNodeData(definition_name=outline.name, kind="row"),
                expand=True,
            )
            for target_slot, source_path in row.derived_slots:
                row_node.add_leaf(
                    Text(f"=> {target_slot} from {source_path}", style="yellow3"),
                    data=CatalogueNodeData(definition_name=outline.name, kind="derived"),
                )
            if row.suppressible:
                row_node.add_leaf(
                    Text("! suppresses on match", style="red"),
                    data=CatalogueNodeData(definition_name=outline.name, kind="suppression"),
                )

    def _select_definition(self, definition_name: str | None) -> None:
        self._selected_definition = definition_name
        if definition_name is None:
            return
        context = self.query_one("#context", TextArea)
        context.load_text(json.dumps(self._context_template(definition_name), indent=2))

    def _context_template(self, definition_name: str) -> dict[str, Any]:
        compiled = self._runtime.get(definition_name)
        domain = _DOMAIN_BY_TABLE.get(compiled.row_projections[0].profile.cdm_table, "")
        if self._service_mode:
            return {
                "grounded_concept_id": 0,
                "grounded_domain": domain,
                "definition_hint": definition_name,
                "context": {},
            }
        grounded: dict[str, Any] = {"concept_id": 0}
        if domain:
            grounded["domain"] = domain
        return {"grounded": grounded, "source": {}}

    def _show_result(self, view: ProjectionViewData) -> None:
        self.query_one("#result-summary", Static).update(render_summary(view))
        populate_result_tree(self.query_one("#result-tree", Tree), view)


def run_tui(
    runtime: OutputDefinitionRuntime,
    project_fn: ProjectCallable | None = None,
) -> None:
    OutputDefinitionExplorer(runtime, project_fn=project_fn).run()


def cli(argv: list[str] | None = None) -> int:
    import argparse

    from omop_semantics.runtime import OmopSemanticEngine

    parser = argparse.ArgumentParser(prog="omop-semantics tui")
    parser.add_argument("--registry", action="append", default=[], type=Path)
    parser.add_argument("--profiles", action="append", default=[], type=Path)
    args = parser.parse_args(argv)

    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=args.registry,
        profile_paths=args.profiles,
    )
    runtime = engine.build_output_definition_runtime([])
    run_tui(runtime)
    return 0


def _extract_runtime_view(bundle: Any) -> ProjectionViewData:
    return ProjectionViewData(
        status=derive_status(
            has_rows=bool(bundle.rows),
            has_unresolved=bool(bundle.unresolved_fields),
            has_suppressed=bool(bundle.suppressed_rows),
        ),
        rows=[
            (row.row_id, row.profile.cdm_table, dict(row.fields))
            for row in bundle.rows
        ],
        suppressed=[
            (row.row_id, row.reason, row.source_field, row.source_code)
            for row in bundle.suppressed_rows
        ],
        unresolved=list(bundle.unresolved_fields),
        audit_notes=list(bundle.audit_notes),
        definition_name=bundle.definition_name,
        role=bundle.role,
    )


def _extract_service_view(result: Any) -> ProjectionViewData:
    return ProjectionViewData(
        status=result.status,
        rows=[
            (row.row_id, row.table, dict(row.fields))
            for row in result.rows
        ],
        suppressed=[
            (row.row_id, row.reason, row.source_field, row.source_code)
            for row in result.suppressed_rows
        ],
        unresolved=list(result.unresolved_fields),
        audit_notes=list(result.audit_notes),
        definition_name=result.definition_name,
        role=result.role,
    )
