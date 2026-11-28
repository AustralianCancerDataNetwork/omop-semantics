"""Deterministic OMOP CDM projection from versioned shape catalogues."""

from collections.abc import Iterable, Mapping
from importlib.metadata import version
from importlib.resources import as_file
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML, YAMLError

from omop_semantics.profiles import ProjectionProfileRuntime
from omop_semantics.runtime.default_valuesets import runtime
from omop_semantics.runtime.instance_loader import load_profiles
from omop_semantics.runtime.value_sets import RuntimeValueSets
from omop_semantics.utils.paths import instance_resource

from .binding import (
    BindingError,
    BindingIssue,
    BindingIssueCode,
    check_compiled_binding,
)
from .compiler import CompiledShape, ShapeCompiler
from .execution import project
from .models import OmopShape, ShapeBinding
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

__all__ = [
    "BindingError",
    "BindingIssue",
    "BindingIssueCode",
    "BoundRow",
    "CheckStatus",
    "ConstraintCheck",
    "EventLink",
    "IssueCode",
    "LinkDecision",
    "LocalRow",
    "OmopShape",
    "ProjectionIssue",
    "ProjectionResult",
    "ProjectionStatus",
    "ShapeBinding",
    "ShapeLoadError",
    "ShapeRuntime",
    "ValueDecision",
    "VocabularyOracle",
]


class ShapeLoadError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("\n".join(errors))


def _validation_errors(key: str, raw: Any, exc: ValidationError) -> list[str]:
    errors = []
    for item in exc.errors(include_url=False):
        parts: list[str] = []
        value = raw
        for part in item["loc"]:
            if isinstance(part, int):
                value = (
                    value[part]
                    if isinstance(value, list) and part < len(value)
                    else None
                )
                row_name = (
                    value.get("id")
                    if parts == ["rows"] and isinstance(value, dict)
                    else None
                )
                if isinstance(row_name, str):
                    parts.append(row_name)
                else:
                    parts[-1] += f"[{part}]"
                continue
            if (
                isinstance(value, dict)
                and part not in value
                and part in (value.get("kind"), value.get("test"))
            ):
                # The validator includes union tags that do not exist as YAML keys.
                continue
            parts.append(part)
            value = value.get(part) if isinstance(value, dict) else None
        location = f"{key}.{'.'.join(parts)}" if parts else key
        errors.append(f"{location}: {item['msg']}")
    return errors


def _load_layer(
    path: Traversable,
    source: str,
    compiler: ShapeCompiler,
    compiled: dict[str, CompiledShape],
) -> list[str]:
    key = f"{source}: shapes"
    try:
        with path.open(encoding="utf-8") as stream:
            document = YAML(typ="safe").load(stream)
    except (OSError, UnicodeError, YAMLError) as exc:
        return [f"{key}: {exc}"]
    if (
        not isinstance(document, dict)
        or set(document) != {"shapes"}
        or not isinstance(document["shapes"], list)
    ):
        return [f"{key}: expected a catalogue containing a shapes list"]

    errors = []
    seen: set[str] = set()
    for index, raw in enumerate(document["shapes"]):
        name = raw.get("name") if isinstance(raw, dict) else None
        shape_key = f"{key}.{name}" if isinstance(name, str) else f"{key}[{index}]"
        try:
            shape = OmopShape.model_validate(raw)
        except ValidationError as exc:
            errors.extend(_validation_errors(shape_key, raw, exc))
            continue
        if shape.name in seen:
            errors.append(f"{shape_key}: duplicate shape in one layer")
            continue
        seen.add(shape.name)
        try:
            compiled[shape.name] = compiler.compile(shape, source)
        except ValueError as exc:
            errors.append(f"{shape_key}.{exc}")
    return errors


class ShapeRuntime:
    """Discover and project shapes compiled from the default and ordered site layers."""

    def __init__(
        self,
        compiled: Mapping[str, CompiledShape],
        oracle: VocabularyOracle | None,
        registry_version: str,
    ) -> None:
        self._compiled = dict(compiled)
        self._oracle = oracle
        self.registry_version = registry_version

    @classmethod
    def from_yaml_paths(
        cls,
        site_paths: Iterable[Path] = (),
        *,
        default_path: Path | None = None,
        profiles: ProjectionProfileRuntime | None = None,
        registry: RuntimeValueSets = runtime,
        registry_version: str | None = None,
        oracle: VocabularyOracle | None = None,
        external_maps: Mapping[str, Mapping[str, int | float]] | None = None,
    ) -> "ShapeRuntime":
        if profiles is None:
            with as_file(instance_resource("profiles.yaml")) as path:
                profiles = ProjectionProfileRuntime(load_profiles(path))
        compiler = ShapeCompiler(profiles, registry, external_maps or {})
        compiled: dict[str, CompiledShape] = {}
        default = (
            default_path
            if default_path is not None
            else instance_resource("shapes.yaml")
        )
        default_source = (
            str(default_path)
            if default_path is not None
            else "omop_semantics:schema/instances/shapes.yaml"
        )
        errors = _load_layer(default, default_source, compiler, compiled)
        for site in site_paths:
            errors.extend(_load_layer(site, str(site), compiler, compiled))
        if errors:
            raise ShapeLoadError(errors)
        return cls(
            compiled,
            oracle,
            registry_version
            if registry_version is not None
            else version("omop-semantics"),
        )

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._compiled))

    def get(self, name: str) -> OmopShape:
        return self._compiled[name].shape

    def check_binding(self, binding: ShapeBinding) -> tuple[BindingIssue, ...]:
        compiled = self._compiled.get(binding.shape)
        if compiled is None:
            return (BindingIssue(BindingIssueCode.unknown_shape, binding.shape),)
        return check_compiled_binding(compiled, binding)

    def project(
        self, binding: ShapeBinding, record: Mapping[str, Any]
    ) -> ProjectionResult:
        issues = self.check_binding(binding)
        if issues:
            raise BindingError(binding.shape, issues)
        return project(
            self._compiled[binding.shape],
            binding,
            record,
            self._oracle,
            self.registry_version,
        )
