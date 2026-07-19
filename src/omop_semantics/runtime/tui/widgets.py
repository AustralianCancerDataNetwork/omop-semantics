from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from rich.text import Text
from textual.widgets import Tree

_STATUS_STYLES = {
    "ok": "green",
    "partial": "yellow3",
    "suppressed": "red",
    "no_match": "grey70",
    "error": "red",
}


@dataclass(frozen=True)
class ProjectionViewData:
    status: str
    rows: Sequence[tuple[str, str, dict[str, Any]]] = ()
    suppressed: Sequence[tuple[str, str, str, str]] = ()
    unresolved: Sequence[dict[str, Any]] = ()
    audit_notes: Sequence[str] = ()
    definition_name: str | None = None
    role: str | None = None
    message: str | None = None


def render_summary(data: ProjectionViewData) -> Text:
    status_style = _STATUS_STYLES.get(data.status, "white")
    summary = Text()
    summary.append("Status: ", style="bold")
    summary.append(data.status, style=f"bold {status_style}")
    if data.definition_name:
        summary.append(" | Definition: ", style="bold")
        summary.append(data.definition_name)
    if data.role:
        summary.append(" | Role: ", style="bold")
        summary.append(data.role)
    if data.message:
        summary.append(" | ")
        summary.append(data.message, style=status_style)
    return summary


def populate_result_tree(tree: Tree[object], data: ProjectionViewData) -> None:
    tree.clear()
    tree.root.expand()

    if data.message and not data.rows and not data.suppressed and not data.unresolved:
        tree.root.add_leaf(_label(data.message, data.status))
        return

    if data.rows:
        rows_node = tree.root.add(Text("Projected rows", style="bold"), expand=True)
        for row_id, table, fields in data.rows:
            row_node = rows_node.add(_label(f"[ok] {row_id} ({table})", "ok"), expand=True)
            for field, value in sorted(fields.items()):
                row_node.add_leaf(Text(f"{field} = {value}"))

    if data.suppressed:
        suppressed_node = tree.root.add(Text("Suppressed rows", style="bold"), expand=True)
        for row_id, reason, source_field, source_code in data.suppressed:
            row_node = suppressed_node.add(
                _label(f"[suppressed] {row_id}", "suppressed"),
                expand=True,
            )
            row_node.add_leaf(Text(f"reason = {reason}", style="red"))
            row_node.add_leaf(Text(f"source_field = {source_field}"))
            row_node.add_leaf(Text(f"source_code = {source_code}"))

    if data.unresolved:
        unresolved_node = tree.root.add(Text("Unresolved", style="bold"), expand=True)
        for entry in data.unresolved:
            row_id = entry.get("row_id")
            if row_id is not None:
                node = unresolved_node.add(
                    _label(f"[unresolved] {row_id}", "partial"),
                    expand=True,
                )
                for field in entry.get("missing_fields", ()):
                    node.add_leaf(Text(f"missing_field = {field}", style="yellow3"))
                continue

            link = entry.get("link")
            if link is not None:
                label = (
                    f"[unresolved] link {link['source_row']} -> {link['target_row']} "
                    f"({link['relationship_type']})"
                )
                node = unresolved_node.add(_label(label, "partial"), expand=True)
                for row_name in entry.get("missing_rows", ()):
                    node.add_leaf(Text(f"missing_row = {row_name}", style="yellow3"))
                continue

            unresolved_node.add_leaf(_label(str(entry), "partial"))

    if data.audit_notes:
        notes_node = tree.root.add(Text("Audit notes", style="bold"), expand=True)
        for note in data.audit_notes:
            notes_node.add_leaf(Text(note))

    if not tree.root.children:
        tree.root.add_leaf(_label("No projected rows.", data.status))


def _label(text: str, status: str) -> Text:
    return Text(text, style=_STATUS_STYLES.get(status, "white"))
