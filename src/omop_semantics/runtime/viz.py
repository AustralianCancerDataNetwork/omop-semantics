from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from typing import Any, Iterable, Literal

from .output_definitions import (
    CompiledOutputDefinition,
    OutputDefinitionRuntime,
    OutputLinkRule,
)
from .projection import ProjectedOutputBundle
from .renderers import Html

_MERMAID_URL = "https://unpkg.com/mermaid@10.4.0/dist/mermaid.esm.min.mjs"
_ID_RE = re.compile(r"[^0-9a-zA-Z_]")


@dataclass(frozen=True)
class RowOutline:
    row_id: str
    profile_name: str
    cdm_table: str
    derived_slots: tuple[tuple[str, str], ...]
    suppressible: bool


@dataclass(frozen=True)
class DefinitionOutline:
    name: str
    role: str
    rows: tuple[RowOutline, ...]
    links: tuple[OutputLinkRule, ...]


class MermaidIdAllocator:
    """
    Allocate Mermaid-safe ids while keeping collisions visible and deterministic.
    """

    def __init__(self) -> None:
        self._assigned: dict[str, str] = {}
        self._counts: dict[str, int] = {}

    def allocate(self, raw: str) -> str:
        existing = self._assigned.get(raw)
        if existing is not None:
            return existing

        base = _ID_RE.sub("_", raw) or "node"
        count = self._counts.get(base, 0) + 1
        self._counts[base] = count
        allocated = base if count == 1 else f"{base}_{count}"
        self._assigned[raw] = allocated
        return allocated


def escape_mermaid_label(value: object) -> str:
    text = "" if value is None else str(value)
    return escape(text, quote=True).replace("|", "&#124;")


def escape_html_text(value: object) -> str:
    text = "" if value is None else str(value)
    return escape(text, quote=True)


def derive_status(
    *,
    has_rows: bool,
    has_unresolved: bool,
    has_suppressed: bool,
) -> Literal["ok", "partial", "suppressed", "no_match"]:
    if has_rows and has_unresolved:
        return "partial"
    if has_rows:
        return "ok"
    if has_unresolved:
        return "partial"
    if has_suppressed:
        return "suppressed"
    return "no_match"


def describe_definition(compiled: CompiledOutputDefinition) -> DefinitionOutline:
    derived_by_row: dict[str, list[tuple[str, str]]] = {}
    for rule in compiled.derivation_rules:
        derived_by_row.setdefault(rule.target_row, []).append(
            (rule.target_slot, rule.source_field.path)
        )

    rows = tuple(
        RowOutline(
            row_id=row.row_id,
            profile_name=row.profile.name,
            cdm_table=row.profile.cdm_table,
            derived_slots=tuple(derived_by_row.get(row.row_id, ())),
            suppressible=row.special_value_policy is not None,
        )
        for row in compiled.row_projections
    )
    return DefinitionOutline(
        name=compiled.name,
        role=compiled.role,
        rows=rows,
        links=tuple(compiled.link_rules),
    )


def bundle_to_mermaid(bundle: ProjectedOutputBundle) -> str:
    allocator = MermaidIdAllocator()
    lines = [
        "flowchart TD",
        "classDef ok fill:#eef7ee,stroke:#3a3,color:#141;",
        "classDef suppressed fill:#fee,stroke:#c00,stroke-dasharray:5 5,color:#900;",
        "classDef unresolved fill:#ffe9b3,stroke:#a80,stroke-dasharray:2 2,color:#850;",
    ]

    for row in bundle.rows:
        node_id = allocator.allocate(row.row_id)
        lines.append(f'{node_id}["{_bundle_row_label(row)}"]:::ok')

    for row in bundle.suppressed_rows:
        node_id = allocator.allocate(f"suppressed_{row.row_id}")
        label = "<br/>".join(
            [
                escape_mermaid_label(row.row_id),
                f"source_field={escape_mermaid_label(row.source_field)}",
                f"source_code={escape_mermaid_label(row.source_code)}",
                f"reason={escape_mermaid_label(row.reason)}",
            ]
        )
        lines.append(f'{node_id}["{label}"]:::suppressed')

    for entry in bundle.unresolved_fields:
        row_id = entry.get("row_id")
        if row_id is None:
            continue
        node_id = allocator.allocate(f"unresolved_{row_id}")
        missing_fields = ", ".join(entry.get("missing_fields", ()))
        label = "<br/>".join(
            [
                escape_mermaid_label(row_id),
                f"missing_fields={escape_mermaid_label(missing_fields)}",
            ]
        )
        lines.append(f'{node_id}["{label}"]:::unresolved')

    for link in bundle.links:
        source_id = allocator.allocate(link.source_row)
        target_id = allocator.allocate(link.target_row)
        lines.append(
            f"{source_id} -->|{escape_mermaid_label(link.relationship_type)}| {target_id}"
        )

    for entry in bundle.unresolved_fields:
        link = entry.get("link")
        if link is None:
            continue
        source_id = allocator.allocate(link["source_row"])
        target_id = allocator.allocate(link["target_row"])
        label = escape_mermaid_label(f'unresolved: {link["relationship_type"]}')
        lines.append(f'{source_id} -. "{label}" .-> {target_id}')

    return "\n".join(lines)


def bundle_to_html(bundle: ProjectedOutputBundle, *, title: str | None = None) -> Html:
    page_title = title or f"Projection: {bundle.definition_name}"
    notes = "".join(
        f"<li>{escape_html_text(note)}</li>" for note in bundle.audit_notes
    )
    extra_html = f"<h2>Audit notes</h2><ul>{notes}</ul>"
    return _html_document(page_title, bundle_to_mermaid(bundle), extra_html=extra_html)


def catalogue_to_mermaid(
    runtime: OutputDefinitionRuntime,
    names: Iterable[str] | None = None,
) -> str:
    allocator = MermaidIdAllocator()
    lines = ["flowchart TD"]

    selected_names = tuple(names) if names is not None else runtime.names()
    for definition_name in selected_names:
        compiled = runtime.get(definition_name)
        outline = describe_definition(compiled)
        subgraph_id = allocator.allocate(outline.name)
        lines.append(f'subgraph {subgraph_id}["{escape_mermaid_label(outline.name)}"]')

        row_ids: dict[str, str] = {}
        for row in outline.rows:
            node_raw = f"{outline.name}_{row.row_id}"
            node_id = allocator.allocate(node_raw)
            row_ids[row.row_id] = node_id
            lines.append(
                f'{node_id}["{escape_mermaid_label(row.row_id)}<br/>'
                f'({escape_mermaid_label(row.cdm_table)} / {escape_mermaid_label(row.profile_name)})"]'
            )

        for link in outline.links:
            lines.append(
                f"{row_ids[link.source_row]} -->|{escape_mermaid_label(link.relationship_type)}| "
                f"{row_ids[link.target_row]}"
            )

        for index, rule in enumerate(compiled.derivation_rules, start=1):
            source_id = allocator.allocate(
                f"{outline.name}_{rule.target_row}_derivation_{rule.target_slot}_{index}"
            )
            lines.append(f'{source_id}["{escape_mermaid_label(rule.source_field.path)}"]')
            lines.append(
                f'{source_id} -. "&#8658; {escape_mermaid_label(rule.target_slot)}" .-> '
                f'{row_ids[rule.target_row]}'
            )

        for index, row in enumerate(compiled.row_projections, start=1):
            policy = row.special_value_policy
            if policy is None:
                continue
            source_id = allocator.allocate(
                f"{outline.name}_{row.row_id}_suppression_{index}"
            )
            allowed = ", ".join(sorted(policy.allowed_special_values))
            lines.append(
                f'{source_id}["{escape_mermaid_label(policy.source_field.path)}<br/>'
                f'{escape_mermaid_label(allowed)}"]'
            )
            lines.append(
                f'{source_id} -. "suppresses on match" .-> {row_ids[row.row_id]}'
            )

        lines.append("end")

    return "\n".join(lines)


def catalogue_to_html(
    runtime: OutputDefinitionRuntime,
    names: Iterable[str] | None = None,
    *,
    title: str | None = None,
) -> Html:
    page_title = title or "Output Definition Catalogue"
    return _html_document(
        page_title,
        catalogue_to_mermaid(runtime, names=names),
        extra_html="",
    )


def _bundle_row_label(row: Any) -> str:
    lines = [
        escape_mermaid_label(row.row_id),
        f"({escape_mermaid_label(row.profile.cdm_table)})",
    ]
    for field, value in sorted(row.fields.items()):
        lines.append(f"{escape_mermaid_label(field)}={escape_mermaid_label(value)}")
    return "<br/>".join(lines)


def _html_document(title: str, mermaid_source: str, *, extra_html: str) -> Html:
    escaped_title = escape_html_text(title)
    return Html(
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{escaped_title}</title>"
        "<script type=\"module\">"
        f'import mermaid from "{_MERMAID_URL}";'
        "mermaid.initialize({ startOnLoad: true });"
        "</script>"
        "<style>body{font-family:system-ui,sans-serif;margin:2rem}.mermaid{margin:1.5rem 0}</style>"
        "</head><body>"
        f"<p><small>This page loads Mermaid from a CDN when available. Offline or CSP-restricted viewers will show raw Mermaid text instead.</small></p>"
        f"<h1>{escaped_title}</h1>"
        "<pre class=\"mermaid\">"
        f"{mermaid_source}"
        "</pre>"
        f"{extra_html}"
        "</body></html>"
    )
