from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .projection import (
    ProjectedOutputBundle,
    ProjectedOutputLink,
    ProjectedOutputRow,
    ProjectionProfileRuntime,
    RuntimeProjectionProfile,
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
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompiledRowProjection:
    row_id: str
    profile: RuntimeProjectionProfile
    field_bindings: Mapping[str, BindingValue]
    defaults: Mapping[str, Any]
    required: bool = True


@dataclass(frozen=True)
class CompiledOutputDefinition:
    name: str
    role: str
    template_names: tuple[str, ...]
    row_projections: tuple[CompiledRowProjection, ...]
    link_rules: tuple[OutputLinkRule, ...]
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
        audit_notes = list(compiled.notes)

        for row_projection in compiled.row_projections:
            resolved_fields = dict(row_projection.defaults)
            missing_fields: list[str] = []

            for slot, binding in row_projection.field_bindings.items():
                found, value = _resolve_binding(binding, context)
                if not found:
                    missing_fields.append(slot)
                    continue
                resolved_fields[slot] = value

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

            compiled_rows.append(
                CompiledRowProjection(
                    row_id=row_projection.row_id,
                    profile=profile,
                    field_bindings=dict(row_projection.field_bindings),
                    defaults=dict(row_projection.defaults),
                    required=row_projection.required,
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
