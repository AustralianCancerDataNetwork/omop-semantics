from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .projection import (
    ProjectedOutputBundle,
    ProjectedOutputLink,
    ProjectedOutputRow,
    ProjectionProfileRuntime,
    RuntimeProjectionProfile,
    SuppressedRow,
)


@dataclass(frozen=True)
class ContextFieldRef:
    """
    Reference to a value in the projection context.

    The path is dot-delimited, for example:

    - `grounded.concept_id`
    - `source.numeric_value`
    - `modifiers.intent_concept_id`
    """

    path: str


BindingValue = Any | ContextFieldRef


class _NoDefault:
    def __repr__(self) -> str:
        return "NO_DEFAULT"


NO_DEFAULT: Any = _NoDefault()
"""Sentinel distinguishing "no default configured" from a configured default of `None`."""


@dataclass(frozen=True)
class DerivationRule:
    """
    Resolve one row's slot value from a source field other than the one that
    grounded the row's entity concept, via a source-code lookup — with an
    explicit escape hatch for codes that should suppress the row entirely.

    This is the n:1 fan-in counterpart to `field_bindings` (which only ever
    read from the same context a row's own entity concept was grounded from).
    The canonical case is a diagnosis paired with a separately-collected
    role/status field (e.g. Primary/Contributing/Non-contributing): the role
    field is never grounded on its own, and its raw code either resolves
    `condition_status_concept_id` via `code_map` or, for "Non-contributing",
    drops the record entirely via `suppress_codes`.
    """

    target_row: str
    target_slot: str
    source_field: ContextFieldRef
    code_map: Mapping[str, Any] = field(default_factory=dict)
    suppress_codes: frozenset[str] = frozenset()
    default: Any = NO_DEFAULT


SUPPRESSION_MODES = frozenset({"drop", "fail", "keep_as_value", "keep_as_modifier"})
"""Recognized `SpecialValuePolicy.suppression_mode` values.

Only `drop` and `fail` have runtime behavior today — both are the degenerate,
single-field case validated against real data (a "meets criteria for X" Yes/No
item, where the negative answer carries no positive clinical content of its
own). `keep_as_value` and `keep_as_modifier` are named here per the schema
proposal so definitions can be authored against a stable enum, but they raise
`NotImplementedError` if actually triggered — there is no validated use case
yet for what they should bind.
"""


@dataclass(frozen=True)
class SpecialValuePolicy:
    """
    Row-level suppression (or other handling) driven by the row's *own*
    source value — the counterpart to `DerivationRule`, which reads a
    different source field. Attach to `OutputRowProjection.special_value_policy`.

    The canonical case is a Yes/No field phrased "meets criteria for X": Yes
    grounds the row normally, No means nothing should be written for it. There
    is no sibling field to consult, so no `DerivationRule` is involved — the
    same value used to ground the row is checked against
    `allowed_special_values`.
    """

    source_field: ContextFieldRef
    allowed_special_values: frozenset[str] = frozenset()
    suppression_mode: str = "drop"


@dataclass(frozen=True)
class OutputRowProjection:
    """
    Declarative row projection definition.
    """

    row_id: str
    profile_name: str
    field_bindings: Mapping[str, BindingValue] = field(default_factory=dict)
    defaults: Mapping[str, Any] = field(default_factory=dict)
    required: bool = True
    special_value_policy: SpecialValuePolicy | None = None


@dataclass(frozen=True)
class OutputLinkRule:
    """
    Declarative relationship between projected rows.
    """

    source_row: str
    target_row: str
    relationship_type: str
    source_field: str | None = None
    target_field: str | None = None


@dataclass(frozen=True)
class OutputDefinition:
    """
    Minimal programmatic output definition.

    This is intentionally additive and runtime-only for the first execution
    slice. It provides enough structure to compile and deterministically
    project rows before a dedicated YAML/schema authoring surface is added.
    """

    name: str
    role: str
    template_names: tuple[str, ...] = ()
    row_projections: tuple[OutputRowProjection, ...] = ()
    link_rules: tuple[OutputLinkRule, ...] = ()
    derivation_rules: tuple[DerivationRule, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompiledRowProjection:
    row_id: str
    profile: RuntimeProjectionProfile
    field_bindings: Mapping[str, BindingValue]
    defaults: Mapping[str, Any]
    required: bool = True
    special_value_policy: SpecialValuePolicy | None = None


@dataclass(frozen=True)
class CompiledOutputDefinition:
    name: str
    role: str
    template_names: tuple[str, ...]
    row_projections: tuple[CompiledRowProjection, ...]
    link_rules: tuple[OutputLinkRule, ...]
    derivation_rules: tuple[DerivationRule, ...]
    notes: tuple[str, ...]


class OutputDefinitionRuntime:
    """
    Compiler and executor for programmatic output definitions.
    """

    def __init__(
        self,
        definitions: Iterable[OutputDefinition],
        projection_profiles: ProjectionProfileRuntime,
    ) -> None:
        self.projection_profiles = projection_profiles
        self._compiled_by_name: dict[str, CompiledOutputDefinition] = {}
        self._compiled_by_template: dict[str, list[CompiledOutputDefinition]] = {}
        for definition in definitions:
            compiled = self._compile_definition(definition)
            if compiled.name in self._compiled_by_name:
                raise ValueError(f"Duplicate output definition name: '{compiled.name}'")
            self._compiled_by_name[compiled.name] = compiled
            for template_name in compiled.template_names:
                self._compiled_by_template.setdefault(template_name, []).append(compiled)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._compiled_by_name))

    def get(self, name: str) -> CompiledOutputDefinition:
        return self._compiled_by_name[name]

    def for_template(self, template_name: str) -> list[CompiledOutputDefinition]:
        return list(self._compiled_by_template.get(template_name, ()))

    def project(self, definition_name: str, context: Mapping[str, Any]) -> ProjectedOutputBundle:
        compiled = self.get(definition_name)
        projected_rows: list[ProjectedOutputRow] = []
        row_ids: set[str] = set()
        unresolved_fields: list[dict[str, Any]] = []
        suppressed_rows: list[SuppressedRow] = []
        audit_notes = list(compiled.notes)

        for row_projection in compiled.row_projections:
            resolved_fields = dict(row_projection.defaults)
            missing_fields: list[str] = []
            row_suppressed = False

            for slot, binding in row_projection.field_bindings.items():
                found, value = _resolve_binding(binding, context)
                if not found:
                    missing_fields.append(slot)
                    continue
                resolved_fields[slot] = value

            for rule in compiled.derivation_rules:
                if rule.target_row != row_projection.row_id:
                    continue

                found, raw_value = _resolve_binding(rule.source_field, context)
                if not found:
                    missing_fields.append(rule.target_slot)
                    continue

                code = str(raw_value)
                if code in rule.suppress_codes:
                    suppressed_rows.append(
                        SuppressedRow(
                            row_id=row_projection.row_id,
                            reason=(
                                f"derivation rule for '{rule.target_slot}' matched a "
                                f"suppress code on '{rule.source_field.path}'"
                            ),
                            source_field=rule.source_field.path,
                            source_code=code,
                        )
                    )
                    row_suppressed = True
                    break

                if code in rule.code_map:
                    resolved_fields[rule.target_slot] = rule.code_map[code]
                elif rule.default is not NO_DEFAULT:
                    resolved_fields[rule.target_slot] = rule.default
                else:
                    missing_fields.append(rule.target_slot)

            policy = row_projection.special_value_policy
            if policy is not None:
                found, raw_value = _resolve_binding(policy.source_field, context)
                if found:
                    code = str(raw_value)
                    if code in policy.allowed_special_values:
                        if policy.suppression_mode == "drop":
                            suppressed_rows.append(
                                SuppressedRow(
                                    row_id=row_projection.row_id,
                                    reason=(
                                        "special_value_policy matched "
                                        f"'{policy.source_field.path}' == '{code}'"
                                    ),
                                    source_field=policy.source_field.path,
                                    source_code=code,
                                )
                            )
                            row_suppressed = True
                        elif policy.suppression_mode == "fail":
                            raise ValueError(
                                f"row '{row_projection.row_id}' hit special value '{code}' "
                                f"on '{policy.source_field.path}', configured to fail"
                            )
                        else:
                            raise NotImplementedError(
                                f"suppression_mode '{policy.suppression_mode}' has no "
                                "runtime behavior yet"
                            )

            if row_suppressed:
                continue

            if missing_fields:
                unresolved_fields.append(
                    {
                        "row_id": row_projection.row_id,
                        "missing_fields": missing_fields,
                        "required": row_projection.required,
                    }
                )
                if row_projection.required:
                    continue

            if row_projection.profile.concept_slot not in resolved_fields:
                unresolved_fields.append(
                    {
                        "row_id": row_projection.row_id,
                        "missing_fields": [row_projection.profile.concept_slot],
                        "required": row_projection.required,
                    }
                )
                if row_projection.required:
                    continue

            row = ProjectedOutputRow(
                row_id=row_projection.row_id,
                profile=row_projection.profile,
                fields=resolved_fields,
            )
            projected_rows.append(row)
            row_ids.add(row.row_id)

        links: list[ProjectedOutputLink] = []
        for link_rule in compiled.link_rules:
            if link_rule.source_row in row_ids and link_rule.target_row in row_ids:
                links.append(
                    ProjectedOutputLink(
                        source_row=link_rule.source_row,
                        target_row=link_rule.target_row,
                        relationship_type=link_rule.relationship_type,
                        source_field=link_rule.source_field,
                        target_field=link_rule.target_field,
                    )
                )
            else:
                unresolved_fields.append(
                    {
                        "link": {
                            "source_row": link_rule.source_row,
                            "target_row": link_rule.target_row,
                            "relationship_type": link_rule.relationship_type,
                        },
                        "missing_rows": [
                            row_id
                            for row_id in (link_rule.source_row, link_rule.target_row)
                            if row_id not in row_ids
                        ],
                    }
                )

        return ProjectedOutputBundle(
            definition_name=compiled.name,
            role=compiled.role,
            rows=projected_rows,
            links=links,
            unresolved_fields=unresolved_fields,
            suppressed_rows=suppressed_rows,
            audit_notes=audit_notes,
        )

    def project_for_template(
        self,
        template_name: str,
        context: Mapping[str, Any],
        *,
        definition_name: str | None = None,
    ) -> ProjectedOutputBundle:
        matches = self.for_template(template_name)
        if definition_name is not None:
            matches = [item for item in matches if item.name == definition_name]
        if not matches:
            raise KeyError(f"No output definition found for template '{template_name}'")
        if len(matches) > 1:
            names = ", ".join(sorted(item.name for item in matches))
            raise ValueError(
                f"Multiple output definitions match template '{template_name}': {names}"
            )
        return self.project(matches[0].name, context)

    def _compile_definition(self, definition: OutputDefinition) -> CompiledOutputDefinition:
        row_ids: set[str] = set()
        compiled_rows: list[CompiledRowProjection] = []
        profile_by_row: dict[str, RuntimeProjectionProfile] = {}
        errors: list[str] = []

        for row_projection in definition.row_projections:
            if row_projection.row_id in row_ids:
                errors.append(f"duplicate row_id '{row_projection.row_id}'")
                continue
            row_ids.add(row_projection.row_id)

            profile = self.projection_profiles.get(row_projection.profile_name)
            declared_slots = set(row_projection.defaults) | set(row_projection.field_bindings)
            invalid_slots = sorted(slot for slot in declared_slots if not profile.allows_slot(slot))
            if invalid_slots:
                errors.append(
                    f"row '{row_projection.row_id}' uses slots not present in profile "
                    f"'{profile.name}': {invalid_slots}"
                )
                continue

            policy = row_projection.special_value_policy
            if policy is not None and policy.suppression_mode not in SUPPRESSION_MODES:
                errors.append(
                    f"row '{row_projection.row_id}' has special_value_policy with "
                    f"unrecognized suppression_mode '{policy.suppression_mode}'; "
                    f"expected one of {sorted(SUPPRESSION_MODES)}"
                )
                continue

            profile_by_row[row_projection.row_id] = profile
            compiled_rows.append(
                CompiledRowProjection(
                    row_id=row_projection.row_id,
                    profile=profile,
                    field_bindings=dict(row_projection.field_bindings),
                    defaults=dict(row_projection.defaults),
                    required=row_projection.required,
                    special_value_policy=policy,
                )
            )

        for link_rule in definition.link_rules:
            if link_rule.source_row not in row_ids:
                errors.append(
                    f"link rule references unknown source_row '{link_rule.source_row}'"
                )
            if link_rule.target_row not in row_ids:
                errors.append(
                    f"link rule references unknown target_row '{link_rule.target_row}'"
                )

        for derivation_rule in definition.derivation_rules:
            if derivation_rule.target_row not in row_ids:
                errors.append(
                    "derivation rule references unknown target_row "
                    f"'{derivation_rule.target_row}'"
                )
                continue
            profile = profile_by_row.get(derivation_rule.target_row)
            if profile is not None and not profile.allows_slot(derivation_rule.target_slot):
                errors.append(
                    f"derivation rule for row '{derivation_rule.target_row}' targets slot "
                    f"'{derivation_rule.target_slot}' not present in profile '{profile.name}'"
                )

        if errors:
            raise ValueError(
                f"Output definition '{definition.name}' failed validation:\n"
                + "\n".join(f"  - {item}" for item in errors)
            )

        return CompiledOutputDefinition(
            name=definition.name,
            role=definition.role,
            template_names=tuple(definition.template_names),
            row_projections=tuple(compiled_rows),
            link_rules=tuple(definition.link_rules),
            derivation_rules=tuple(definition.derivation_rules),
            notes=tuple(definition.notes),
        )


def _resolve_binding(binding: BindingValue, context: Mapping[str, Any]) -> tuple[bool, Any]:
    if isinstance(binding, ContextFieldRef):
        return _resolve_context_path(context, binding.path)
    return True, binding


def _resolve_context_path(context: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = context
    for part in path.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return False, None
            current = current[part]
            continue
        if not hasattr(current, part):
            return False, None
        current = getattr(current, part)
    return True, current
