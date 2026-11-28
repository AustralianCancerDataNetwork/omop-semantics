from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from omop_semantics.profiles import (
    ProjectedOutputRow as ProjectedOutputRow,
    ProjectionProfileRuntime as ProjectionProfileRuntime,
    RuntimeProjectionProfile as RuntimeProjectionProfile,
)


@dataclass(frozen=True)
class SuppressedRow:
    """
    A row a definition would have produced, dropped deterministically by a
    `DerivationRule` or row-level suppression policy rather than fabricated
    with a missing or null slot value.
    """

    row_id: str
    reason: str
    source_field: str
    source_code: str


@dataclass(frozen=True)
class ProjectedOutputLink:
    """
    Relationship between projected rows.
    """

    source_row: str
    target_row: str
    relationship_type: str
    source_field: str | None = None
    target_field: str | None = None


@dataclass(frozen=True)
class ProjectedOutputBundle:
    """
    Transport-friendly deterministic projection result.
    """

    definition_name: str
    role: str
    rows: list[ProjectedOutputRow]
    links: list[ProjectedOutputLink] = field(default_factory=list)
    constraint_checks: list[dict[str, Any]] = field(default_factory=list)
    unresolved_fields: list[dict[str, Any]] = field(default_factory=list)
    suppressed_rows: list[SuppressedRow] = field(default_factory=list)
    audit_notes: list[str] = field(default_factory=list)

    def row(self, row_id: str) -> ProjectedOutputRow:
        for row in self.rows:
            if row.row_id == row_id:
                return row
        raise KeyError(f"No projected row with id '{row_id}'")

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_name": self.definition_name,
            "role": self.role,
            "rows": [
                {
                    "row_id": row.row_id,
                    "profile": row.profile.name,
                    "cdm_table": row.profile.cdm_table,
                    "fields": dict(row.fields),
                }
                for row in self.rows
            ],
            "links": [
                {
                    "source_row": link.source_row,
                    "target_row": link.target_row,
                    "relationship_type": link.relationship_type,
                    "source_field": link.source_field,
                    "target_field": link.target_field,
                }
                for link in self.links
            ],
            "constraint_checks": [dict(item) for item in self.constraint_checks],
            "unresolved_fields": [dict(item) for item in self.unresolved_fields],
            "suppressed_rows": [
                {
                    "row_id": row.row_id,
                    "reason": row.reason,
                    "source_field": row.source_field,
                    "source_code": row.source_code,
                }
                for row in self.suppressed_rows
            ],
            "audit_notes": list(self.audit_notes),
        }
