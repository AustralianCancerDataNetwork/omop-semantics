"""Resolve and validate authoring references before projecting any record."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from types import MappingProxyType

from omop_semantics.links import LINK_MECHANISMS, LinkMechanism, field_concept_id
from omop_semantics.profiles import (
    ProjectionProfileRuntime,
    RuntimeProjectionProfile,
)
from omop_semantics.runtime.value_sets import RuntimeSemanticUnit, RuntimeValueSets
from omop_semantics.unknowns import UNKNOWN

from .models import (
    BindingMap,
    Coded,
    CodeMap,
    ConceptMapEntry,
    Constraint,
    ExternalMap,
    Input,
    Link,
    MembershipPredicate,
    Numeric,
    NumericFromCode,
    NumericWithUnit,
    OmopShape,
    Ordinal,
    PartialDate,
    Predicate,
    RegistryLabelMap,
    RoleInput,
    Row,
    UnitPolicy,
)


@dataclass(frozen=True)
class CompiledGroup:
    parents: frozenset[int]
    excluded: frozenset[int]


@dataclass(frozen=True)
class CompiledConstraint:
    rule: Constraint
    exact: frozenset[int] = frozenset()
    groups: tuple[CompiledGroup, ...] = ()


@dataclass(frozen=True)
class CompiledMap:
    values: Mapping[str, int | float]
    binding_codes: tuple[tuple[str, int], ...] = ()
    external: tuple[str, str] | None = None


@dataclass(frozen=True)
class CompiledUnits:
    allowed: frozenset[int] | None
    canonical: int | None
    conversions: Mapping[int, tuple[float, float]]


@dataclass(frozen=True)
class CompiledRow:
    row: Row
    profile: RuntimeProjectionProfile
    concept_id: int | None
    constraints: tuple[CompiledConstraint, ...]
    value_map: CompiledMap | None
    ordinal: tuple[int, ...]
    units: CompiledUnits | None
    derivation_maps: tuple[CompiledMap, ...]


@dataclass(frozen=True)
class CompiledLink:
    link: Link
    mechanism: LinkMechanism
    target_table: str
    field_concept: int


@dataclass(frozen=True)
class CompiledShape:
    shape: OmopShape
    rows: tuple[CompiledRow, ...]
    links: tuple[CompiledLink, ...]
    source: str


def require(condition: object, key: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{key}: {message}")


class ShapeCompiler:
    def __init__(
        self,
        profiles: ProjectionProfileRuntime,
        registry: RuntimeValueSets,
        external_maps: Mapping[str, Mapping[str, int | float]],
    ) -> None:
        self.profiles = profiles
        self.registry = registry
        self.external_maps = external_maps

    def compile(self, shape: OmopShape, source: str) -> CompiledShape:
        rows = {row.id: row for row in shape.rows}
        require(len(rows) == len(shape.rows), "rows", "duplicate row id")
        for namespace in (
            "roles",
            "context",
            "optional_roles",
            "optional_context",
            "code_groups",
        ):
            names = getattr(shape, namespace)
            require(len(set(names)) == len(names), namespace, "duplicate name")
        for namespace in ("roles", "context"):
            require(
                set(getattr(shape, f"optional_{namespace}"))
                <= set(getattr(shape, namespace)),
                f"optional_{namespace}",
                "optional names must be declared in the namespace",
            )

        compiled = tuple(self._row(row, shape) for row in shape.rows)
        profiles = {row.row.id: row.profile for row in compiled}
        links = tuple(
            self._link(link, index, shape, profiles)
            for index, link in enumerate(shape.links)
        )
        fields = {
            (link.link.source_row, link.mechanism.event_id_column) for link in links
        }
        require(
            len(fields) == len(links), "links", "multiple links write the same fields"
        )
        return CompiledShape(shape, compiled, links, source)

    def _profile(self, name: str, key: str) -> RuntimeProjectionProfile:
        try:
            return self.profiles.get(name)
        except KeyError:
            raise ValueError(f"{key}: unknown CDM profile {name!r}") from None

    def _unit(self, reference: str, key: str) -> RuntimeSemanticUnit:
        parts = reference.split(".")
        require(len(parts) == 2, key, f"expected value_set.unit, got {reference!r}")
        try:
            return self.registry[parts[0]].members[parts[1]]
        except KeyError:
            raise ValueError(f"{key}: unknown semantic unit {reference!r}") from None

    def _concept(self, reference: str, key: str) -> int:
        unit, _, label = reference.rpartition(".")
        try:
            return self._unit(unit, key).exact_mapper()[label]
        except KeyError:
            raise ValueError(f"{key}: unknown exact concept {reference!r}") from None

    def _constraint(self, rule: Constraint, key: str) -> CompiledConstraint:
        ref = rule.reference
        if ref is None or rule.kind == "domain":
            return CompiledConstraint(rule)
        if rule.kind == "exact":
            return CompiledConstraint(rule, exact=frozenset({self._concept(ref, key)}))

        unit = self._unit(ref, key)
        if rule.kind == "members":
            require(unit.exact_ids, key, "semantic unit has no exact members")
            return CompiledConstraint(rule, exact=frozenset(unit.exact_ids))

        groups = tuple(
            CompiledGroup(
                frozenset(group.parent_ids), frozenset(group.excluded_parent_ids)
            )
            for group in unit.groups.values()
            if group.parent_ids
        )
        exact = frozenset(unit.exact_ids) if rule.kind == "composite" else frozenset()
        require(groups or exact, key, "semantic unit has no descendant anchors")
        return CompiledConstraint(rule, exact, groups)

    def _map(
        self, mapping: CodeMap, shape: OmopShape, key: str, *, numeric: bool
    ) -> CompiledMap:
        if isinstance(mapping, RegistryLabelMap):
            require(not numeric, key, "registry labels map to concepts")
            values = self._unit(mapping.registry_labels, key).exact_mapper()
            require(values, key, "semantic unit has no exact members")
            return CompiledMap(MappingProxyType(values))

        if isinstance(mapping, ExternalMap):
            return self._external_map(mapping.external_map, key, numeric=numeric)

        if isinstance(mapping, BindingMap):
            require(not numeric, key, "binding code groups map to concepts")
            groups = {}
            for entry in mapping.binding_codes:
                require(
                    entry.codes_from in shape.code_groups,
                    key,
                    f"unknown code group {entry.codes_from!r}",
                )
                require(
                    entry.codes_from not in groups,
                    key,
                    f"duplicate code group {entry.codes_from!r}",
                )
                groups[entry.codes_from] = self._concept(entry.concept, key)
            return CompiledMap(MappingProxyType({}), tuple(groups.items()))

        entries: dict[str, int | float] = {}
        for entry in mapping.code_map:
            entry_key = f"{key}.code_map[{entry.code}]"
            require(entry.code not in entries, entry_key, "duplicate code")
            if numeric and not isinstance(entry, ConceptMapEntry):
                entries[entry.code] = entry.number
            elif not numeric and isinstance(entry, ConceptMapEntry):
                entries[entry.code] = self._concept(entry.concept, entry_key)
            else:
                raise ValueError(
                    f"{entry_key}: expected {'a number' if numeric else 'a concept reference'}"
                )
        return CompiledMap(MappingProxyType(entries))

    def _external_map(self, name: str, key: str, *, numeric: bool) -> CompiledMap:
        require(name in self.external_maps, key, f"unknown external map {name!r}")
        values = dict(self.external_maps[name])
        for code, value in values.items():
            valid = (
                self._valid_number(value)
                if numeric
                else (type(value) is int and value >= 0)
            )
            require(
                isinstance(code, str) and valid, key, f"invalid entry for code {code!r}"
            )
        canonical = json.dumps(
            values, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return CompiledMap(
            MappingProxyType(values),
            external=(name, sha256(canonical.encode()).hexdigest()),
        )

    @staticmethod
    def _valid_number(value: int | float) -> bool:
        try:
            return type(value) in (int, float) and isfinite(value)
        except OverflowError:
            return False

    @staticmethod
    def _input(ref: Input | None, shape: OmopShape, key: str) -> None:
        if isinstance(ref, RoleInput):
            require(ref.role in shape.roles, key, f"unknown role {ref.role!r}")
        elif ref is not None:
            require(
                ref.context in shape.context, key, f"unknown context {ref.context!r}"
            )

    def _predicate(self, pred: Predicate | None, shape: OmopShape, key: str) -> None:
        if pred is not None:
            self._input(pred.source, shape, f"{key}.source")
        if isinstance(pred, MembershipPredicate):
            for group in pred.codes_from:
                require(
                    group in shape.code_groups,
                    f"{key}.codes_from",
                    f"unknown code group {group!r}",
                )

    def _row(self, row: Row, shape: OmopShape) -> CompiledRow:
        key = f"rows.{row.id}"
        profile = self._profile(row.profile, f"{key}.profile")
        concept_id = None
        if isinstance(row.concept, str):
            concept_id = self._concept(row.concept, f"{key}.concept")
        else:
            self._input(row.concept, shape, f"{key}.concept")
        constraints = tuple(
            self._constraint(rule, f"{key}.constraints[{index}]")
            for index, rule in enumerate(row.constraints)
        )

        value_map, ordinal, units = self._value(row, profile, shape, f"{key}.value")
        self._context(row, profile, shape, f"{key}.context")
        self._predicate(row.suppress_when, shape, f"{key}.suppress_when")
        for index, policy in enumerate(row.special_values):
            policy_key = f"{key}.special_values[{index}]"
            self._predicate(policy.when, shape, f"{policy_key}.when")
            self._input(policy.source, shape, f"{policy_key}.source")
            if policy.mode == "keep_as_value":
                require(
                    profile.value_slot == "value_as_concept_id",
                    policy_key,
                    "requires a coded value slot",
                )
                require(
                    policy.unknown in UNKNOWN,
                    f"{policy_key}.unknown",
                    "give a registered unknown label",
                )
            else:
                require(
                    policy.unknown is None,
                    f"{policy_key}.unknown",
                    "only keep_as_value writes an unknown",
                )

        derivations = self._derivations(row, profile, shape, key)
        return CompiledRow(
            row,
            profile,
            concept_id,
            constraints,
            value_map,
            ordinal,
            units,
            derivations,
        )

    def _context(
        self, row: Row, profile: RuntimeProjectionProfile, shape: OmopShape, key: str
    ) -> None:
        require(
            not row.context.event_date or profile.event_date_slot,
            f"{key}.event_date",
            "profile has no date slot",
        )
        for index, source in enumerate(row.context.event_date):
            item = f"{key}.event_date[{index}]"
            self._input(source.source, shape, f"{item}.source")
            self._predicate(source.when, shape, f"{item}.when")
        for field in ("visit", "care_site"):
            ref = getattr(row.context, field)
            require(
                ref is None or getattr(profile, f"{field}_slot"),
                f"{key}.{field}",
                "profile has no slot",
            )
            self._input(ref, shape, f"{key}.{field}")

    def _value(
        self,
        row: Row,
        profile: RuntimeProjectionProfile,
        shape: OmopShape,
        key: str,
    ) -> tuple[CompiledMap | None, tuple[int, ...], CompiledUnits | None]:
        value = row.value
        if value.kind == "presence":
            return None, (), None
        if isinstance(value, PartialDate):
            require(
                profile.value_slot == "value_as_string",
                key,
                "profile must have value slot value_as_string",
            )
            for name in ("year", "month", "day"):
                self._input(getattr(value, name), shape, f"{key}.{name}")
            return None, (), None

        self._input(value.source, shape, f"{key}.source")
        if isinstance(value, (Coded, Ordinal)):
            require(
                profile.value_slot == "value_as_concept_id",
                key,
                "profile must have value slot value_as_concept_id",
            )
            return self._coded(value, shape, key)

        require(
            profile.value_slot == "value_as_number",
            key,
            "profile must have value slot value_as_number",
        )
        if isinstance(value, NumericFromCode):
            return (
                self._map(value.mapping, shape, f"{key}.mapping", numeric=True),
                (),
                None,
            )
        if isinstance(value, (Numeric, NumericWithUnit)):
            self._input(value.operator, shape, f"{key}.operator")
            require(
                value.operator is None or profile.operator_slot,
                f"{key}.operator",
                "profile has no operator slot",
            )
        if isinstance(value, NumericWithUnit):
            require(profile.unit_slot, f"{key}.unit", "profile has no unit slot")
            for name in ("range_low", "range_high"):
                source = getattr(value, name)
                self._input(source, shape, f"{key}.{name}")
                require(
                    source is None or name in profile.numeric_slots,
                    f"{key}.{name}",
                    "profile has no range slot",
                )
            return None, (), self._units(value.unit, shape, f"{key}.unit")
        return None, (), None

    def _coded(
        self, value: Coded | Ordinal, shape: OmopShape, key: str
    ) -> tuple[CompiledMap | None, tuple[int, ...], None]:
        mapping = (
            self._map(value.mapping, shape, f"{key}.mapping", numeric=False)
            if value.mapping is not None
            else None
        )
        if isinstance(value, Coded):
            return mapping, (), None
        order = tuple(self._concept(ref, f"{key}.order") for ref in value.order)
        require(
            len(set(order)) == len(order), f"{key}.order", "duplicate ordinal concepts"
        )
        if mapping is not None:
            targets = set(mapping.values.values()) | {
                concept for _, concept in mapping.binding_codes
            }
            require(
                set(order).issuperset(targets),
                f"{key}.mapping",
                "map has unordered concepts",
            )
        return mapping, order, None

    def _units(self, policy: UnitPolicy, shape: OmopShape, key: str) -> CompiledUnits:
        self._input(policy.source, shape, f"{key}.source")
        allowed = None
        if policy.allowed is not None:
            allowed = frozenset(self._unit(policy.allowed, f"{key}.allowed").exact_ids)
            require(allowed, f"{key}.allowed", "semantic unit has no exact members")
        canonical = (
            self._concept(policy.canonical, f"{key}.canonical")
            if policy.canonical
            else None
        )
        require(
            canonical is None or allowed is None or canonical in allowed,
            f"{key}.canonical",
            "must be allowed",
        )
        conversions = {}
        for rule in policy.conversions:
            unit = self._concept(rule.unit, f"{key}.conversions")
            require(
                unit != canonical and unit not in conversions,
                f"{key}.conversions",
                "duplicate or canonical unit",
            )
            require(
                allowed is None or unit in allowed,
                f"{key}.conversions",
                "unit must be allowed",
            )
            conversions[unit] = (rule.factor, rule.offset)
        return CompiledUnits(allowed, canonical, MappingProxyType(conversions))

    def _derivations(
        self, row: Row, profile: RuntimeProjectionProfile, shape: OmopShape, key: str
    ) -> tuple[CompiledMap, ...]:
        targets: set[str] = set()
        maps = []
        for index, rule in enumerate(row.derivations):
            item = f"{key}.derivations[{index}]"
            self._input(rule.source, shape, f"{item}.source")
            self._predicate(rule.when, shape, f"{item}.when")
            slot = rule.target_slot
            require(
                slot not in targets,
                f"{item}.target_slot",
                "duplicate derivation target",
            )
            numeric = slot in profile.numeric_slots
            concept = slot in profile.extra_concept_slots
            require(
                concept or numeric,
                f"{item}.target_slot",
                f"{slot!r} is not a derivable slot in {profile.name}",
            )
            require(
                not (
                    slot in ("range_low", "range_high")
                    and getattr(row.value, slot, None) is not None
                ),
                f"{item}.target_slot",
                "also supplied by value input",
            )
            targets.add(slot)
            maps.append(
                self._map(rule.mapping, shape, f"{item}.mapping", numeric=numeric)
            )
        return tuple(maps)

    def _link(
        self,
        link: Link,
        index: int,
        shape: OmopShape,
        profiles: Mapping[str, RuntimeProjectionProfile],
    ) -> CompiledLink:
        key = f"links[{index}]"
        require(link.source_row in profiles, f"{key}.source_row", "unknown row")
        require(
            link.mechanism in LINK_MECHANISMS,
            f"{key}.mechanism",
            "unknown link mechanism",
        )
        mechanism = LINK_MECHANISMS[link.mechanism]
        require(
            mechanism.linking_table == profiles[link.source_row].cdm_table,
            f"{key}.mechanism",
            "source row has the wrong CDM table",
        )
        self._predicate(link.when, shape, f"{key}.when")
        if link.target_row is not None:
            require(
                link.target_row in profiles and link.target_row != link.source_row,
                f"{key}.target_row",
                "unknown target or self link",
            )
            table = profiles[link.target_row].cdm_table
        else:
            self._input(link.target_item, shape, f"{key}.target_item")
            assert link.target_table is not None
            table = link.target_table.value
        try:
            field_concept = field_concept_id(table)
        except ValueError as exc:
            raise ValueError(f"{key}: {exc}") from exc
        return CompiledLink(link, mechanism, table, field_concept)
