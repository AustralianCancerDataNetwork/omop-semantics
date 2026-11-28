"""Row fragments and structured validation results."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Protocol

from omop_semantics.links import LinkMechanism
from omop_semantics.profiles import ProjectedOutputRow
from omop_semantics.unknowns import UnknownReason

from .models import ConstraintKind, SpecialMode


class VocabularyOracle(Protocol):
    def is_descendant(self, concept_id: int, ancestor_id: int) -> bool: ...
    def is_standard(self, concept_id: int) -> bool: ...
    def domain_of(self, concept_id: int) -> str | None: ...


class ProjectionStatus(StrEnum):
    ok = "ok"
    partial = "partial"
    suppressed = "suppressed"
    invalid = "invalid"


class CheckStatus(StrEnum):
    passed = "passed"
    deferred = "deferred"
    failed = "failed"


class IssueCode(StrEnum):
    missing_input = "missing_input"
    invalid_input = "invalid_input"
    unmapped_code = "unmapped_code"
    missing_link_target = "missing_link_target"
    special_value_failed = "special_value_failed"


@dataclass(frozen=True)
class ConstraintCheck:
    row: str
    slot: str
    kind: ConstraintKind
    concept_id: int
    reference: str | None
    status: CheckStatus


@dataclass(frozen=True)
class ProjectionIssue:
    row: str
    slot: str
    code: IssueCode


@dataclass(frozen=True)
class ValueDecision:
    row: str
    mode: SpecialMode
    source_code: str | None
    reason: UnknownReason | None = None


@dataclass(frozen=True)
class LinkDecision:
    """An inactive link whose local target was deliberately suppressed."""

    source: str
    target: str
    suppressed_source: bool


@dataclass(frozen=True)
class BoundRow:
    """A previously materialized CDM row supplied through a binding."""

    table: str
    id: int

    def __post_init__(self) -> None:
        if type(self.id) is not int or self.id <= 0:
            raise ValueError("BoundRow needs a positive CDM row id")


@dataclass(frozen=True)
class LocalRow:
    """A projected row whose CDM identifier is assigned by the caller."""

    row: str


@dataclass(frozen=True)
class EventLink:
    source: str
    target: BoundRow | LocalRow
    mechanism: LinkMechanism
    field_concept_id: int

    @property
    def fields(self) -> dict[str, int | LocalRow]:
        event_id = self.target.id if isinstance(self.target, BoundRow) else self.target
        return {
            self.mechanism.event_id_column: event_id,
            self.mechanism.field_concept_column: self.field_concept_id,
        }


@dataclass(frozen=True)
class ProjectionResult:
    shape: str
    shape_version: str
    registry_version: str
    status: ProjectionStatus
    rows: tuple[ProjectedOutputRow, ...]
    links: tuple[EventLink, ...]
    constraint_checks: tuple[ConstraintCheck, ...]
    issues: tuple[ProjectionIssue, ...]
    value_decisions: tuple[ValueDecision, ...]
    link_decisions: tuple[LinkDecision, ...]
    shape_source: str
    maps: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "shape": self.shape,
            "shape_version": self.shape_version,
            "registry_version": self.registry_version,
            "shape_source": self.shape_source,
            "maps": dict(self.maps),
            "status": self.status.value,
            "rows": [
                {
                    "row_id": row.row_id,
                    "profile": row.profile.name,
                    "cdm_table": row.profile.cdm_table,
                    **(
                        {"value_rank": row.value_rank}
                        if row.value_rank is not None
                        else {}
                    ),
                    "fields": {
                        key: value.isoformat() if isinstance(value, date) else value
                        for key, value in row.fields.items()
                    },
                }
                for row in self.rows
            ],
            "links": [
                {
                    "source": link.source,
                    "target": asdict(link.target),
                    "mechanism": link.mechanism.name,
                    "table": link.mechanism.linking_table,
                    "fields": {
                        key: asdict(value) if isinstance(value, LocalRow) else value
                        for key, value in link.fields.items()
                    },
                }
                for link in self.links
            ],
            "constraint_checks": [asdict(check) for check in self.constraint_checks],
            "issues": [asdict(issue) for issue in self.issues],
            "value_decisions": [asdict(decision) for decision in self.value_decisions],
            "link_decisions": [asdict(decision) for decision in self.link_decisions],
        }
