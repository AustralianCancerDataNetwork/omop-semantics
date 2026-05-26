from __future__ import annotations

from pathlib import Path
import yaml
from omop_semantics.schema.registry import ConceptRecord, ConceptGroupRecord, ConceptRegistry
from dataclasses import dataclass
from typing import Sequence

from omop_semantics.schema.schema_model import SchemaInfo, load_schema_info

from .instance_manager import load_instances_any 


def load_yaml_instances(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

@dataclass(frozen=True)
class LoadOptions:
    validate: bool = True
    # If True, insist that roles exist in schema; if False, allow unknown roles.
    strict_roles: bool = True
    # If True, require that all parents exist in registry after load.
    strict_parents: bool = True
    # If True, require that all group members exist.
    strict_group_members: bool = True


def load(
    *,
    schema_paths: Sequence[str | Path],
    instance_paths: Sequence[str | Path],
    options: LoadOptions = LoadOptions(),
) -> ConceptRegistry:
    """
    Load a ConceptRegistry from LinkML schema YAML + LinkML instance YAML.

    This remains the public compatibility API for older registry-oriented
    workflows. Newer shape-aware runtime work should generally prefer
    `omop_semantics.runtime`.
    """
    schema_paths = [Path(p) for p in schema_paths]
    instance_paths = [Path(p) for p in instance_paths]

    schema = load_schema_info(*schema_paths)
    concepts, groups = load_instances_any(*instance_paths)

    reg = ConceptRegistry(concepts=concepts, groups=groups, schema=schema)

    if options.validate:
        reg.validate(
            strict_roles=options.strict_roles,
            strict_parents=options.strict_parents,
            strict_group_members=options.strict_group_members,
        )
    return reg
