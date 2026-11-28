"""Validate persisted wiring against a compiled catalogue."""

from dataclasses import dataclass
from enum import StrEnum

from .compiler import CompiledShape
from .models import ShapeBinding


class BindingIssueCode(StrEnum):
    unknown_shape = "unknown_shape"
    unknown_role = "unknown_role"
    unknown_context = "unknown_context"
    unbound_role = "unbound_role"
    unbound_context = "unbound_context"
    unknown_code_group = "unknown_code_group"
    unbound_code_group = "unbound_code_group"
    ambiguous_code = "ambiguous_code"


@dataclass(frozen=True)
class BindingIssue:
    code: BindingIssueCode
    name: str


class BindingError(ValueError):
    def __init__(self, shape: str, issues: tuple[BindingIssue, ...]) -> None:
        self.issues = issues
        detail = ", ".join(f"{issue.code} {issue.name!r}" for issue in issues)
        super().__init__(f"binding for {shape!r}: {detail}")


def _ambiguous_codes(shape: CompiledShape, binding: ShapeBinding) -> set[str]:
    ambiguous: set[str] = set()
    for row in shape.rows:
        for mapping in (row.value_map, *row.derivation_maps):
            if mapping is None:
                continue
            seen: set[str] = set()
            for group, _ in mapping.binding_codes:
                codes = set(binding.codes.get(group, ()))
                ambiguous.update(seen & codes)
                seen.update(codes)
    return ambiguous


def check_compiled_binding(
    compiled: CompiledShape, binding: ShapeBinding
) -> tuple[BindingIssue, ...]:
    shape = compiled.shape
    requirements = (
        (binding.roles, set(shape.roles), set(shape.optional_roles), "role"),
        (
            binding.context,
            set(shape.context),
            set(shape.optional_context),
            "context",
        ),
        (binding.codes, set(shape.code_groups), set(), "code_group"),
    )
    issues = []
    for supplied, declared, optional, kind in requirements:
        issues.extend(
            BindingIssue(BindingIssueCode(f"unknown_{kind}"), name)
            for name in sorted(supplied.keys() - declared)
        )
        issues.extend(
            BindingIssue(BindingIssueCode(f"unbound_{kind}"), name)
            for name in sorted(declared - supplied.keys() - optional)
        )
    issues.extend(
        BindingIssue(BindingIssueCode.ambiguous_code, code)
        for code in sorted(_ambiguous_codes(compiled, binding))
    )
    return tuple(issues)
