"""
Runtime accessors for OMOP semantic value sets.

This module provides a lightweight, interactive runtime layer over declarative
OMOP semantic registries defined using LinkML schemas and YAML instance files.
It exposes semantic enums, groups, and concepts as Python attribute-accessible
namespaces, with rich ``repr`` and ``_repr_html_`` renderings for notebook
exploration.

The runtime API is designed for:

- Interactive exploration of available semantic objects in Jupyter
- Readable rule logic (e.g. ``runtime.genomic.genomic_value_group.genomic_positive``)
- Debugging and documentation of registry content
- Safe programmatic access to OMOP concept identifiers

The core abstractions are:

- ``RuntimeEnum``: wraps an ``OmopEnum`` as a label-concept_id namespace
- ``RuntimeGroup``: wraps an ``OmopGroup`` as a label-concept_id namespace
- ``RuntimeSemanticUnit``: aggregates enums, groups, and concepts under one unit
- ``RuntimeValueSet``: groups semantic units into named value sets
- ``RuntimeValueSets``: top-level registry namespace

This layer intentionally avoids mutability and database concerns and is intended
as a pure read-only semantic access layer.
"""

import warnings
from abc import ABC
from dataclasses import dataclass
from typing import Mapping, TypeVar

from omop_semantics.schema.generated_models.omop_named_sets import (
    CDMSemanticUnits,
    CDMValueSet,
    CDMValueSets,
    OmopConcept,
    OmopEnum,
    OmopGroup,
    OmopSemanticObject,
)
from .renderers import Html, h, table, tr


class _RuntimeLabelledConcepts(ABC):
    """
    Thin shared base for runtime objects that expose a label -> concept_id mapping.
    """

    _by_label: Mapping[str, int]
    _name: str

    kind_label: str = "Concepts"   # overridden in subclasses
    kind_tag: str = "RuntimeConcepts"

    @property
    def labels(self) -> list[str]:
        return sorted(self._by_label.keys())

    @property
    def ids(self) -> set[int]:
        return set(self._by_label.values())

    def mapper(self) -> dict[str, int]:
        return dict(self._by_label)

    def __getattr__(self, label: str) -> int:
        if label.startswith("_"):
            raise AttributeError(label)
        try:
            return self._by_label[label]
        except KeyError:
            raise AttributeError(label) from None

    def __repr__(self) -> str:
        labels = ", ".join(self.labels)
        return f"{self.kind_tag}({self._name}: [{labels}])"

    def _repr_html_(self) -> str:
        rows = [tr([label, cid]) for label, cid in sorted(self._by_label.items())]
        return Html(
            f"<h4>{h(self.kind_label)}: {h(self._name)}</h4>"
            + table(rows, header=["Label", "Concept ID"])
        ).raw

class RuntimeGroup(_RuntimeLabelledConcepts):
    """
    Runtime wrapper around an ``OmopGroup``.

    Exposes descendant-expanding parent concepts and excluded parent concepts
    as an attribute-accessible namespace. Use the role-specific accessors when
    passing concepts to downstream vocabulary expansion. ``ids`` and
    ``mapper()`` are deprecated parent-only compatibility aliases.

    This allows interactive access such as:

        >>> runtime.staging.t_stage_concepts.t3
        1634376

    """

    kind_label = "Group"
    kind_tag = "RuntimeGroup"

    def __init__(self, group: OmopGroup):
        self._group = group
        self._name = group.name or '[group]'
        self._included_by_label = {
            c.label: c.concept_id
            for c in (group.parent_concepts or [])
            if c and c.label and c.concept_id
        }
        self._excluded_by_label = {
            c.label: c.concept_id
            for c in (group.excluded_parent_concepts or [])
            if c and c.label and c.concept_id
        }
        self._by_label = self._included_by_label | self._excluded_by_label

    @property
    def parent_ids(self) -> set[int]:
        return set(self._included_by_label.values())

    @property
    def excluded_parent_ids(self) -> set[int]:
        return set(self._excluded_by_label.values())

    def parent_mapper(self) -> dict[str, int]:
        return dict(self._included_by_label)

    def excluded_parent_mapper(self) -> dict[str, int]:
        return dict(self._excluded_by_label)

    @property
    def ids(self) -> set[int]:
        warnings.warn(
            "RuntimeGroup.ids is deprecated; use parent_ids for "
            "descendant-expanding anchors.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parent_ids

    @property
    def excluded_ids(self) -> set[int]:
        warnings.warn(
            "RuntimeGroup.excluded_ids is deprecated; use excluded_parent_ids.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.excluded_parent_ids

    def mapper(self) -> dict[str, int]:
        warnings.warn(
            "RuntimeGroup.mapper() is deprecated; use parent_mapper().",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parent_mapper()

    def excluded_mapper(self) -> dict[str, int]:
        warnings.warn(
            "RuntimeGroup.excluded_mapper() is deprecated; use "
            "excluded_parent_mapper().",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.excluded_parent_mapper()

    @property
    def is_singleton(self) -> bool:
        return len(self._included_by_label) == 1
    
    @property
    def value(self) -> int:
        """
        Return the sole concept_id if this group has exactly one parent.
        """
        if not self.is_singleton:
            raise AttributeError(
                f"Group '{self._group.name}' has multiple parent concepts"
            )
        return next(iter(self._included_by_label.values()))
    
    def __int__(self) -> int:
        """
        Allow int(runtime.group) for singleton groups.
        """
        return self.value

    def _repr_html_(self) -> str:
        rows = [
            tr([label, cid, "Parent anchor"])
            for label, cid in sorted(self._included_by_label.items())
        ]
        rows.extend(
            tr([label, cid, "Excluded parent anchor"])
            for label, cid in sorted(self._excluded_by_label.items())
        )
        return Html(
            f"<h4>{h(self.kind_label)}: {h(self._name)}</h4>"
            + table(rows, header=["Label", "Concept ID", "Role"])
        ).raw

class RuntimeEnum(_RuntimeLabelledConcepts):

    """
    Runtime wrapper around an ``OmopEnum``.

    Exposes enum members as a label to concept_id mapping, accessible via
    attribute access:

        >>> runtime.genomic.genomic_value_group.genomic_positive
        9191

    Attributes
    ----------
    labels : list[str]
        Sorted list of enum labels.
    ids : set[int]
        Complete set of exact concept IDs in the enum.

    """

    kind_label = "Enum"
    kind_tag = "RuntimeEnum"

    def __init__(self, enum: OmopEnum):
        self._enum = enum
        self._name = enum.name or '[enum]'
        self._by_label = {
            m.label: m.concept_id
            for m in enum.enum_members
            if m.concept_id and m.label
        }
        

class RuntimeConcept:
    def __init__(self, concept: OmopConcept):
        self._concept = concept

    @property
    def value(self) -> int | None:
        return self._concept.concept_id

    @property
    def values(self) -> set[int]:
        return {self.value if self.value else 0}

class RuntimeSemanticUnit:

    """
    Runtime container for a single semantic unit.

    A semantic unit may contain any combination of:

    - Named enums (``RuntimeEnum``)
    - Named groups (``RuntimeGroup``)
    - Named concepts (raw ``OmopConcept``)

    This class exposes:

    - Direct access to named enums/groups/concepts via attributes
    - Direct access to enum/group labels as attributes (flattened lookup)
    - Rich textual and HTML representations for introspection

    Example
    -------
        >>> runtime.genomic.genomic_value_group.genomic_positive
        9191

        >>> runtime.staging.t_stage_concepts.t4
        1634654
    """

    def __init__(self, unit: CDMSemanticUnits):
        self._unit = unit
        self.enums = {
            enum.name: RuntimeEnum(enum)
            for enum in (unit.named_enumerators or [])
            if enum and enum.name
        }
        self.groups = {
            group.name: RuntimeGroup(group)
            for group in (unit.named_groups or [])
            if group and group.name
        }
        self.concepts = {
            concept.name: concept
            for concept in (unit.named_concepts or [])
            if concept and concept.name
        }
        self._validate_flattened_labels()

    def _validate_flattened_labels(self) -> None:
        """Reject labels whose flattened attribute lookup would be ambiguous."""
        owners: dict[str, str] = {}

        for kind, items in (("enum", self.enums), ("group", self.groups)):
            for item_name, item in items.items():
                for label in item.labels:
                    owner = f"{kind} '{item_name}'"
                    if previous := owners.get(label):
                        raise ValueError(
                            f"Semantic unit '{self._unit.name}' exposes label '{label}' "
                            f"from both {previous} and {owner}"
                        )
                    owners[label] = owner

        for concept_name in self.concepts:
            owner = f"concept '{concept_name}'"
            if previous := owners.get(concept_name):
                raise ValueError(
                    f"Semantic unit '{self._unit.name}' exposes label "
                    f"'{concept_name}' from both {previous} and {owner}"
                )
            owners[concept_name] = owner

    def _single_group(self) -> RuntimeGroup | None:
        if len(self.groups) > 1:
            raise ValueError(
                f"Semantic unit '{self._unit.name}' has multiple groups; "
                "role-specific group composition requires at most one"
            )
        return next(iter(self.groups.values()), None)

    @property
    def parent_ids(self) -> set[int]:
        """Return descendant-expanding anchors from the unit's governed group."""
        group = self._single_group()
        return group.parent_ids if group else set()

    @property
    def excluded_parent_ids(self) -> set[int]:
        """Return excluded descendant-expanding anchors from the governed group."""
        group = self._single_group()
        return group.excluded_parent_ids if group else set()

    @property
    def exact_ids(self) -> set[int]:
        """Return exact members declared by enums and named concepts."""
        vals: set[int] = set()
        for enum in self.enums.values():
            vals |= enum.ids
        for concept in self.concepts.values():
            if concept.concept_id is not None:
                vals.add(concept.concept_id)
        return vals

    def parent_mapper(self) -> dict[str, int]:
        group = self._single_group()
        return group.parent_mapper() if group else {}

    def excluded_parent_mapper(self) -> dict[str, int]:
        group = self._single_group()
        return group.excluded_parent_mapper() if group else {}

    def exact_mapper(self) -> dict[str, int]:
        mapped: dict[str, int] = {}
        for enum in self.enums.values():
            mapped.update(enum.mapper())
        for name, concept in self.concepts.items():
            if concept.concept_id is not None:
                mapped[concept.label or name] = concept.concept_id
        return mapped

    @property
    def ids(self) -> set[int]:
        if self.groups:
            warnings.warn(
                "RuntimeSemanticUnit.ids is deprecated for group-backed units; "
                "use parent_ids, exact_ids, and excluded_parent_ids.",
                DeprecationWarning,
                stacklevel=2,
            )
        parent_ids = {
            concept_id
            for group in self.groups.values()
            for concept_id in group.parent_ids
        }
        return parent_ids | self.exact_ids

    def __getattr__(self, name: str):
        if name in self.enums:
            return self.enums[name]
        if name in self.groups:
            g = self.groups[name]
            if g.is_singleton:
                return g.value
            return g
        if name in self.concepts:
            return self.concepts[name]

        for labelled_item in [self.enums, self.groups]:
            for value in labelled_item.values():
                try:
                    return getattr(value, name)
                except AttributeError:
                    pass

        raise AttributeError(name) from None

    def __repr__(self) -> str:
        parts = []
        if self.enums:
            parts.append(f"enums={list(self.enums.keys())}")
        if self.groups:
            parts.append(f"groups={list(self.groups.keys())}")
        if self.concepts:
            parts.append(f"concepts={list(self.concepts.keys())}")

        inner = ", ".join(parts) if parts else "empty"
        return f"RuntimeSemanticUnit({self._unit.name}: {inner})"

    def _repr_html_(self) -> str:
        rows = []
        for name in sorted(self.enums):
            labels = ", ".join(self.enums[name]._by_label)
            rows.append(tr(["Enum (exact)", name, labels]))
        for name, g in sorted(self.groups.items()):
            labels = list(g._included_by_label)
            labels.extend(f"not {label}" for label in g._excluded_by_label)
            if labels:
                rows.append(tr(["Group (descendants)", name, ", ".join(labels)]))
        for name in sorted(self.concepts):
            rows.append(tr(["Concept (exact)", name, ""]))

        notes = getattr(self._unit, "notes", None)
        return Html(
            f"<h3>Semantic Unit: {h(self._unit.name)}</h3>"
            + (f"<p>{h(notes)}</p>" if notes else "")
            + table(rows, header=["Type", "Name", "Members"])
        ).raw
    
    def __dir__(self):
        names = set(self.enums) | set(self.groups) | set(self.concepts)

        for enum in self.enums.values():
            names |= set(enum._by_label.keys())

        for group in self.groups.values():
            names |= set(group._by_label.keys())

        return sorted(set(super().__dir__()) | names)

@dataclass(frozen=True)
class RuntimeValueSet:

    """
    Runtime representation of a named value set.

    A value set groups multiple semantic units under a single namespace or 
    conceptual module - no added functionality just for ease of access and use

    (e.g. ``genomic``, ``staging``, ``modifiers``).

    Semantic units can be accessed via attribute lookup:

        >>> runtime.genomic.genomic_value_group
        RuntimeSemanticUnit(...)

    """

    name: str
    members: dict[str, RuntimeSemanticUnit]


    @property
    def ids(self) -> set[int]:
        vals: set[int] = set()
        for vs in self.members.values():
            vals |= vs.ids
        return vals

    def __getattr__(self, name: str) -> RuntimeSemanticUnit:
        try:
            return self.members[name]
        except KeyError:
            raise AttributeError(name)
        
    def __repr__(self) -> str:
        keys = ", ".join(sorted(self.members.keys()))
        return f"RuntimeValueSet({self.name}: [{keys}])"

    def _repr_html_(self) -> str:
        rows = [
            tr([name, 
                ", ".join(unit.enums.keys()),
                ", ".join(unit.groups.keys()),
                ", ".join(unit.concepts.keys())])
            for name, unit in sorted(self.members.items())
        ]

        return Html(
            f"<h2>ValueSet: {h(self.name)}</h2>"
            + table(rows, header=["Semantic Unit", "Enums", "Groups", "Concepts"])
        ).raw
    
    def __dir__(self):
        return sorted(set(super().__dir__()) | set(self.members.keys()))
    

class RuntimeValueSets:

    """
    Top-level runtime namespace for all compiled value sets.

    This is the primary entry point for interactive access to the semantic
    registry:

        >>> runtime.genomic
        >>> runtime.staging
        >>> runtime.nlp

    Each attribute corresponds to a named ``RuntimeValueSet``.

    """

    def __init__(self, valuesets: dict[str, RuntimeValueSet]):
        self._valuesets = valuesets

    def __getattr__(self, name: str) -> RuntimeValueSet:
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return self._valuesets[name]
        except KeyError:
            raise AttributeError(name) from None

    def __repr__(self) -> str:
        keys = ", ".join(sorted(self._valuesets.keys()))
        return f"RuntimeValueSets([{keys}])"

    def _repr_html_(self) -> str:
        
        rows = [
            tr([name, ", ".join(sorted(vs.members.keys()))])
            for name, vs in sorted(self._valuesets.items())
        ]

        return Html(
            "<h1>OMOP Semantic Registry</h1>"
            + table(rows, header=["ValueSet", "Semantic Units"])
        ).raw
    
    def __dir__(self):
        return sorted(set(super().__dir__()) | set(self._valuesets.keys()))
    
  
def compile_valuesets(defs: CDMValueSets) -> RuntimeValueSets:

    """
    Compile declarative CDM value set definitions into runtime objects.

    Parameters
    ----------
    defs : CDMValueSets
        Parsed value set definitions after interpolation.

    Returns
    -------
    RuntimeValueSets
        Runtime-accessible registry of all value sets and semantic units.

    Notes
    -----
    This step materialises the interactive runtime namespace used in notebooks
    and rule logic. It is intentionally pure and read-only.
    """

    compiled: dict[str, RuntimeValueSet] = {}

    for vs in defs.valuesets:
        members = {
            (unit.name or "[unlabelled]"): RuntimeSemanticUnit(unit)
            for unit in vs.semantic_units
        }

        compiled[vs.valueset_name] = RuntimeValueSet(
            name=vs.valueset_name,
            members=members,
        )

    return RuntimeValueSets(compiled)


def index_semantic_units(units: CDMSemanticUnits) -> dict[str, OmopSemanticObject]:
    """
    Build a name → semantic object index from a ``CDMSemanticUnits`` container.

    Parameters
    ----------
    units : CDMSemanticUnits
        Declarative semantic unit registry.

    Returns
    -------
    dict[str, OmopSemanticObject]
        Mapping from semantic unit name to underlying OMOP semantic object
        (enum, group, or concept).

    This index is used during interpolation of value set definitions.
    """

    index: dict[str, OmopSemanticObject] = {}

    for e in units.named_enumerators or []:
        if e.name:
            index[e.name] = e

    for g in units.named_groups or []:
        if g.name:
            index[g.name] = g

    for c in units.named_concepts or []:
        if c.name:
            index[c.name] = c

    return index


_COMPOSITE_REFERENCE_FIELDS = frozenset(
    {"named_enumerators", "named_groups", "named_concepts"}
)
_ALLOWED_COMPOSITE_FIELDS = _COMPOSITE_REFERENCE_FIELDS.union(
    {"name", "notes"}
)
SemanticObjectT = TypeVar("SemanticObjectT", OmopEnum, OmopGroup, OmopConcept)


def _semantic_object(
    reference: str,
    semantic_index: dict[str, OmopSemanticObject],
) -> OmopSemanticObject:
    try:
        return semantic_index[reference]
    except KeyError:
        raise KeyError(
            f"Unknown semantic unit referenced in valuesets.yaml: {reference}"
        ) from None


def _unit_from_object(name: str, obj: OmopSemanticObject) -> CDMSemanticUnits:
    if isinstance(obj, OmopEnum):
        return CDMSemanticUnits(name=name, named_enumerators=[obj])
    if isinstance(obj, OmopGroup):
        return CDMSemanticUnits(name=name, named_groups=[obj])
    if isinstance(obj, OmopConcept):
        return CDMSemanticUnits(name=name, named_concepts=[obj])
    raise TypeError(f"Unsupported semantic unit type: {type(obj)}")


def _composite_unit(
    member: dict,
    semantic_index: dict[str, OmopSemanticObject],
) -> CDMSemanticUnits:
    unexpected = set(member) - _ALLOWED_COMPOSITE_FIELDS
    if unexpected:
        raise ValueError(
            "Unsupported composite semantic-unit fields: "
            f"{', '.join(sorted(unexpected))}"
        )

    name = member.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("Composite semantic units require a non-empty name")

    notes = member.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise TypeError(f"Composite semantic unit '{name}' notes must be a string")

    def typed_references(
        field: str,
        expected_type: type[SemanticObjectT],
    ) -> list[SemanticObjectT]:
        references = member.get(field, [])
        if not isinstance(references, list) or not all(
            isinstance(reference, str) for reference in references
        ):
            raise TypeError(
                f"Composite semantic unit '{name}' field '{field}' "
                "must be a list of string references"
            )
        resolved: list[SemanticObjectT] = []
        for reference in references:
            obj = _semantic_object(reference, semantic_index)
            if not isinstance(obj, expected_type):
                raise TypeError(
                    f"Composite semantic unit '{name}' references '{reference}' "
                    f"under '{field}', but it is {type(obj).__name__}"
                )
            resolved.append(obj)
        return resolved

    named_enums = typed_references("named_enumerators", OmopEnum)
    named_groups = typed_references("named_groups", OmopGroup)
    named_concepts = typed_references("named_concepts", OmopConcept)

    if len(named_groups) > 1:
        raise ValueError(
            f"Composite semantic unit '{name}' may reference at most one group"
        )

    if not (named_enums or named_groups or named_concepts):
        raise ValueError(
            f"Composite semantic unit '{name}' must reference at least one object"
        )

    return CDMSemanticUnits(
        name=name,
        notes=notes,
        named_enumerators=named_enums,
        named_groups=named_groups,
        named_concepts=named_concepts,
    )


def interpolate_valuesets(
    raw: dict,
    semantic_index: dict[str, OmopSemanticObject],
) -> CDMValueSets:
    """
    Interpolate value set definitions by resolving simple or composite references.

    A string member keeps the compact one-object-per-unit form. A mapping can
    compose one named semantic unit from references in ``named_groups``,
    ``named_enumerators``, and ``named_concepts``. Composite units intentionally
    permit at most one group so parent exclusions retain one unambiguous scope.

    Parameters
    ----------
    raw : dict
        Raw parsed YAML dictionary from ``valuesets.yaml``.
    semantic_index : dict[str, OmopSemanticObject]
        Lookup table mapping semantic unit names to OMOP semantic objects.

    Returns
    -------
    CDMValueSets
        Fully resolved value set definitions suitable for compilation into
        runtime objects.

    Raises
    ------
    KeyError
        If a referenced semantic unit name does not exist.
    TypeError
        If an unsupported semantic object type is encountered.
    """
    valuesets = []

    for vs in raw["valuesets"]:
        resolved_members: list[CDMSemanticUnits] = []

        for member in vs["semantic_units"]:
            if isinstance(member, str):
                obj = _semantic_object(member, semantic_index)
                resolved_members.append(_unit_from_object(member, obj))
            elif isinstance(member, dict):
                resolved_members.append(_composite_unit(member, semantic_index))
            else:
                raise TypeError(
                    "semantic_units entries must be string references or mappings"
                )

        valuesets.append(
            CDMValueSet(
                valueset_name=vs["name"],
                semantic_units=resolved_members,
            )
        )

    return CDMValueSets(valuesets=valuesets)
