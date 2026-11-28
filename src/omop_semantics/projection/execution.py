"""Execute a compiled shape against one bound source record."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from math import isfinite
from numbers import Integral, Real
from types import MappingProxyType
from typing import Any

from omop_semantics.profiles import ProjectedOutputRow
from omop_semantics.unknowns import UNKNOWN

from .compiler import (
    CompiledConstraint,
    CompiledGroup,
    CompiledLink,
    CompiledMap,
    CompiledRow,
    CompiledShape,
    CompiledUnits,
)
from .models import (
    ConstraintKind,
    ContextInput,
    Input,
    MembershipPredicate,
    Numeric,
    NumericWithUnit,
    PartialDate,
    Predicate,
    RoleInput,
    ShapeBinding,
    SpecialMode,
    SpecialValue,
)
from .result import (
    BoundRow,
    CheckStatus,
    ConstraintCheck,
    EventLink,
    IssueCode,
    LinkDecision,
    LocalRow,
    ProjectionIssue,
    ProjectionResult,
    ProjectionStatus,
    ValueDecision,
    VocabularyOracle,
)


class _InputError(ValueError):
    def __init__(self, slot: str, code: IssueCode = IssueCode.invalid_input) -> None:
        self.slot = slot
        self.code = code


def _absent(raw: Any) -> bool:
    if raw is None:
        return True
    if isinstance(raw, str):
        return not raw.strip()
    if isinstance(raw, Real) and not isinstance(raw, Integral):
        return bool(raw != raw)
    scalar = type(raw)
    if scalar.__module__.startswith("pandas.") and scalar.__name__ in (
        "NAType",
        "NaTType",
    ):
        return True
    return (
        scalar.__module__ == "numpy"
        and scalar.__name__ == "datetime64"
        and bool(raw != raw)
    )


def _required(raw: Any, slot: str) -> Any:
    if _absent(raw):
        raise _InputError(slot, IssueCode.missing_input)
    return raw


def _integer(raw: Any, slot: str, minimum: int = 0) -> int:
    raw = _required(raw, slot)
    if isinstance(raw, bool):
        raise _InputError(slot)
    if isinstance(raw, Integral) or (
        isinstance(raw, Real) and isfinite(raw) and raw % 1 == 0
    ):
        value = int(raw)
    elif isinstance(raw, str) and raw.isascii() and raw.isdecimal():
        try:
            value = int(raw)
        except ValueError as exc:
            raise _InputError(slot) from exc
    else:
        raise _InputError(slot)
    if value < minimum:
        raise _InputError(slot)
    return value


def _number(raw: Any, slot: str) -> float:
    raw = _required(raw, slot)
    try:
        if isinstance(raw, bool) or not isinstance(raw, (Real, str)):
            raise ValueError
        value = float(raw)
        if isfinite(value):
            return value
    except (ValueError, OverflowError):
        pass
    raise _InputError(slot)


def _code(raw: Any) -> str | None:
    if _absent(raw):
        return None
    if isinstance(raw, bool) or (
        type(raw).__module__ == "numpy" and type(raw).__name__ in ("bool", "bool_")
    ):
        return "true" if raw else "false"
    if isinstance(raw, Integral) or (
        isinstance(raw, Real) and isfinite(raw) and raw % 1 == 0
    ):
        try:
            return str(int(raw))
        except (ValueError, OverflowError):
            return None
    return raw if isinstance(raw, str) else None


def _event_date(raw: Any, slot: str) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        if isinstance(raw, str) and len(raw) == 10:
            parsed = date.fromisoformat(raw)
            if parsed.isoformat() == raw:
                return parsed
    except ValueError:
        pass
    raise _InputError(slot)


def _group_check(
    group: CompiledGroup, concept: int, oracle: VocabularyOracle | None
) -> CheckStatus:
    if concept in group.excluded:
        return CheckStatus.failed
    if oracle is None:
        if concept in group.parents and not group.excluded:
            return CheckStatus.passed
        return CheckStatus.deferred
    included = concept in group.parents or any(
        oracle.is_descendant(concept, anchor) for anchor in sorted(group.parents)
    )
    excluded = included and any(
        oracle.is_descendant(concept, anchor) for anchor in sorted(group.excluded)
    )
    return CheckStatus.passed if included and not excluded else CheckStatus.failed


def _check(
    check: CompiledConstraint, concept: int, oracle: VocabularyOracle | None
) -> CheckStatus:
    kind = check.rule.kind
    if concept in check.exact:
        return CheckStatus.passed
    if kind in ("exact", "members"):
        return CheckStatus.failed
    if kind in ("composite", "descendants"):
        outcomes = {_group_check(group, concept, oracle) for group in check.groups}
        if CheckStatus.passed in outcomes:
            return CheckStatus.passed
        if CheckStatus.deferred in outcomes:
            return CheckStatus.deferred
        return CheckStatus.failed
    if oracle is None:
        return CheckStatus.deferred
    passes = (
        oracle.is_standard(concept)
        if kind == "standard_only"
        else oracle.domain_of(concept) == check.rule.reference
    )
    return CheckStatus.passed if passes else CheckStatus.failed


@dataclass
class _BoundInputs:
    binding: ShapeBinding
    record: Mapping[str, Any]
    maps: dict[str, str] = field(default_factory=dict, init=False)

    def read(self, source: Input | None) -> Any:
        key = None
        if isinstance(source, RoleInput):
            key = self.binding.roles.get(source.role)
        elif isinstance(source, ContextInput):
            key = self.binding.context.get(source.context)
        return self.record.get(key) if key is not None else None

    def matches(self, predicate: Predicate | None) -> bool:
        if predicate is None:
            return True
        raw = self.read(predicate.source)
        if not isinstance(predicate, MembershipPredicate):
            return _absent(raw) == (predicate.test == "unanswered")
        if _absent(raw):
            return False
        code = _code(raw)
        contained = code in predicate.codes or any(
            code in self.binding.codes[group] for group in predicate.codes_from
        )
        return contained == (predicate.test == "in")

    def mapped(self, raw: Any, mapping: CompiledMap, slot: str) -> int | float:
        if mapping.external is not None:
            name, digest = mapping.external
            self.maps[name] = digest
        code = _code(_required(raw, slot))
        if code is None:
            raise _InputError(slot)
        if code in mapping.values:
            return mapping.values[code]
        for group, concept_id in mapping.binding_codes:
            if code in self.binding.codes[group]:
                return concept_id
        raise _InputError(slot, IssueCode.unmapped_code)


@dataclass
class _Projection:
    inputs: _BoundInputs
    oracle: VocabularyOracle | None
    rows: dict[str, ProjectedOutputRow] = field(default_factory=dict, init=False)
    links: list[EventLink] = field(default_factory=list, init=False)
    checks: list[ConstraintCheck] = field(default_factory=list, init=False)
    issues: list[ProjectionIssue] = field(default_factory=list, init=False)
    decisions: list[ValueDecision] = field(default_factory=list, init=False)
    link_decisions: list[LinkDecision] = field(default_factory=list, init=False)
    suppressed: set[str] = field(default_factory=set, init=False)
    incomplete: bool = field(default=False, init=False)
    failed: bool = field(default=False, init=False)

    def _issue(self, row: str, error: _InputError, *, required: bool = True) -> None:
        self.issues.append(ProjectionIssue(row, error.slot, error.code))
        self.incomplete |= required
        self.failed |= error.code == IssueCode.invalid_input

    def prepare_row(self, compiled: CompiledRow) -> SpecialValue | None:
        row = compiled.row
        if row.suppress_when is not None and self.inputs.matches(row.suppress_when):
            self.decisions.append(
                ValueDecision(
                    row.id,
                    SpecialMode.drop,
                    _code(self.inputs.read(row.suppress_when.source)),
                )
            )
            self.suppressed.add(row.id)
            return None

        policy = next(
            (rule for rule in row.special_values if self.inputs.matches(rule.when)),
            None,
        )
        if policy is not None and policy.mode == "drop":
            self._record_policy(row.id, policy)
            self.suppressed.add(row.id)
        return policy

    def _record_policy(self, row: str, policy: SpecialValue) -> None:
        self.decisions.append(
            ValueDecision(
                row, policy.mode, _code(self.inputs.read(policy.source)), policy.reason
            )
        )

    def suppress_dependent_rows(self, links: tuple[CompiledLink, ...]) -> None:
        required = [
            item.link
            for item in links
            if item.link.target_row is not None
            and item.link.required_target
            and self.inputs.matches(item.link.when)
        ]
        while True:
            dependent = {
                link.source_row
                for link in required
                if link.target_row in self.suppressed
            }
            if dependent <= self.suppressed:
                return
            self.suppressed.update(dependent)

    def emit_row(self, compiled: CompiledRow, policy: SpecialValue | None) -> None:
        row, profile = compiled.row, compiled.profile
        if row.id in self.suppressed:
            return
        if policy is not None:
            self._record_policy(row.id, policy)
        if policy is not None and policy.mode == "fail":
            self.issues.append(
                ProjectionIssue(
                    row.id,
                    profile.value_slot or profile.concept_slot,
                    IssueCode.special_value_failed,
                )
            )
            self.failed = True
            return
        try:
            self._emit_row(compiled, policy)
        except _InputError as exc:
            self._issue(row.id, exc, required=row.required)

    def _emit_row(self, compiled: CompiledRow, policy: SpecialValue | None) -> None:
        row, profile = compiled.row, compiled.profile
        concept = compiled.concept_id
        if not isinstance(row.concept, str):
            concept = _integer(self.inputs.read(row.concept), profile.concept_slot)
        checks = tuple(
            ConstraintCheck(
                row.id,
                profile.concept_slot,
                ConstraintKind(check.rule.kind),
                concept,
                check.rule.reference,
                _check(check, concept, self.oracle),
            )
            for check in compiled.constraints
            if concept is not None
        )
        self.checks.extend(checks)
        if any(check.status == CheckStatus.failed for check in checks):
            self.failed = True
            return

        fields: dict[str, Any] = {profile.concept_slot: concept}
        self._context(compiled, fields)
        if (
            policy is not None
            and policy.unknown is not None
            and profile.value_slot is not None
        ):
            fields[profile.value_slot] = UNKNOWN[policy.unknown].concept_id
        else:
            self._value(compiled, fields)
        self._derive(compiled, fields)

        if (
            compiled.units is not None
            and profile.unit_slot is not None
            and profile.value_slot is not None
        ):
            self._normalize_units(
                compiled.units, fields, profile.unit_slot, profile.value_slot
            )
        if (
            "range_low" in fields
            and "range_high" in fields
            and fields["range_low"] > fields["range_high"]
        ):
            raise _InputError("range_high")
        rank = None
        if compiled.ordinal and profile.value_slot is not None and policy is None:
            rank = compiled.ordinal.index(fields[profile.value_slot]) + 1
        self.rows[row.id] = ProjectedOutputRow(row.id, profile, fields, rank)

    def _derive(self, compiled: CompiledRow, fields: dict[str, Any]) -> None:
        row = compiled.row
        for rule, mapping in zip(
            row.derivations, compiled.derivation_maps, strict=True
        ):
            if not self.inputs.matches(rule.when):
                continue
            try:
                fields[rule.target_slot] = self.inputs.mapped(
                    self.inputs.read(rule.source), mapping, rule.target_slot
                )
            except _InputError as exc:
                self.issues.append(ProjectionIssue(row.id, exc.slot, exc.code))
                self.incomplete |= rule.required

    def _context(self, compiled: CompiledRow, fields: dict[str, Any]) -> None:
        context, profile = compiled.row.context, compiled.profile
        slot = profile.event_date_slot
        if context.event_date and slot is not None:
            for option in context.event_date:
                if self.inputs.matches(option.when):
                    value = self.inputs.read(option.source)
                    if not _absent(value):
                        fields[slot] = _event_date(value, slot)
                        break
            else:
                raise _InputError(slot, IssueCode.missing_input)

        for ref, slot in (
            (context.visit, profile.visit_slot),
            (context.care_site, profile.care_site_slot),
        ):
            if ref is not None and slot is not None:
                fields[slot] = _integer(self.inputs.read(ref), slot, minimum=1)

    def _value(self, compiled: CompiledRow, fields: dict[str, Any]) -> None:
        value, profile = compiled.row.value, compiled.profile
        slot = profile.value_slot
        if value.kind == "presence" or slot is None:
            return
        if isinstance(value, PartialDate):
            fields[slot] = self._partial_date(value, slot)
            return

        raw = self.inputs.read(value.source)
        if compiled.value_map is not None:
            fields[slot] = self.inputs.mapped(raw, compiled.value_map, slot)
        elif value.kind in ("coded", "ordinal"):
            fields[slot] = _integer(raw, slot)
        else:
            fields[slot] = _number(raw, slot)
        if compiled.ordinal and fields[slot] not in compiled.ordinal:
            raise _InputError(slot)

        if isinstance(value, NumericWithUnit) and profile.unit_slot is not None:
            fields[profile.unit_slot] = _integer(
                self.inputs.read(value.unit.source), profile.unit_slot, minimum=1
            )
        if (
            isinstance(value, (Numeric, NumericWithUnit))
            and value.operator is not None
            and profile.operator_slot is not None
        ):
            fields[profile.operator_slot] = _integer(
                self.inputs.read(value.operator), profile.operator_slot
            )
        if not isinstance(value, NumericWithUnit):
            return
        for name, source in (
            ("range_low", value.range_low),
            ("range_high", value.range_high),
        ):
            raw = self.inputs.read(source)
            if not _absent(raw):
                fields[name] = _number(raw, name)

    def _partial_date(self, value: PartialDate, slot: str) -> str:
        year = self._date_component(self.inputs.read(value.year), slot)
        month = self._date_component(self.inputs.read(value.month), slot)
        day = self._date_component(self.inputs.read(value.day), slot)
        if year is None:
            raise _InputError(slot, IssueCode.missing_input)
        if month is None and day is not None:
            raise _InputError(slot)
        try:
            # Validate the components. Emit only the precision actually supplied.
            date(year, month if month is not None else 1, day if day is not None else 1)
        except (ValueError, OverflowError):
            raise _InputError(slot) from None
        if month is None:
            return f"{year:04d}"
        if day is None:
            return f"{year:04d}-{month:02d}"
        return f"{year:04d}-{month:02d}-{day:02d}"

    @staticmethod
    def _date_component(raw: Any, slot: str) -> int | None:
        if _absent(raw):
            return None
        return _integer(raw, slot, minimum=1)

    @staticmethod
    def _normalize_units(
        units: CompiledUnits, fields: dict[str, Any], slot: str, value_slot: str
    ) -> None:
        unit = fields[slot]
        if units.allowed is not None and unit not in units.allowed:
            raise _InputError(slot)
        if units.canonical is None or unit == units.canonical:
            return
        if unit not in units.conversions:
            raise _InputError(slot)
        factor, offset = units.conversions[unit]
        for key in (value_slot, "range_low", "range_high"):
            if key in fields:
                fields[key] = _number(fields[key] * factor + offset, key)
        fields[slot] = units.canonical

    def emit_link(self, compiled: CompiledLink) -> None:
        link = compiled.link
        if not self.inputs.matches(link.when):
            return
        if link.target_row is not None and link.target_row in self.suppressed:
            self.link_decisions.append(
                LinkDecision(link.source_row, link.target_row, link.required_target)
            )
            return
        if link.source_row not in self.rows:
            return
        try:
            target = self._link_target(compiled)
        except _InputError as exc:
            self._issue(link.source_row, exc)
            return
        self.links.append(
            EventLink(
                link.source_row, target, compiled.mechanism, compiled.field_concept
            )
        )

    def _link_target(self, compiled: CompiledLink) -> BoundRow | LocalRow:
        link = compiled.link
        slot = compiled.mechanism.event_id_column
        if link.target_row is not None:
            if link.target_row not in self.rows:
                raise _InputError(slot, IssueCode.missing_link_target)
            return LocalRow(link.target_row)
        raw = self.inputs.read(link.target_item)
        if _absent(raw):
            raise _InputError(slot, IssueCode.missing_link_target)
        if isinstance(raw, Mapping) and set(raw) == {"table", "id"}:
            raw = BoundRow(raw["table"], _integer(raw["id"], slot, minimum=1))
        if not isinstance(raw, BoundRow) or raw.table != compiled.target_table:
            raise _InputError(slot)
        return raw

    def status(self) -> ProjectionStatus:
        if self.failed:
            return ProjectionStatus.invalid
        if self.incomplete or not self.rows and self.issues:
            return ProjectionStatus.partial
        if not self.rows and self.suppressed:
            return ProjectionStatus.suppressed
        return ProjectionStatus.ok


def project(
    shape: CompiledShape,
    binding: ShapeBinding,
    record: Mapping[str, Any],
    oracle: VocabularyOracle | None,
    registry_version: str,
) -> ProjectionResult:
    projection = _Projection(_BoundInputs(binding, record), oracle)
    policies = tuple(projection.prepare_row(row) for row in shape.rows)
    projection.suppress_dependent_rows(shape.links)
    for row, policy in zip(shape.rows, policies, strict=True):
        projection.emit_row(row, policy)
    for link in shape.links:
        projection.emit_link(link)
    return ProjectionResult(
        shape.shape.name,
        shape.shape.version,
        registry_version,
        projection.status(),
        tuple(projection.rows.values()),
        tuple(projection.links),
        tuple(projection.checks),
        tuple(projection.issues),
        tuple(projection.decisions),
        tuple(projection.link_decisions),
        shape.source,
        MappingProxyType(projection.inputs.maps),
    )
