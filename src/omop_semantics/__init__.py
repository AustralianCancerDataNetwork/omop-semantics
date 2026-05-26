"""
Package exports for omop-semantics.

This module currently exposes both:

- the older registry-oriented compatibility API (`load`, `ConceptRegistry`),
- and package path helpers (`BASE_DIR`, `SCHEMA_DIR`, `INSTANCE_DIR`).

New shape-aware runtime work should generally use `omop_semantics.runtime`,
while the exports here remain useful for compatibility with existing
ConceptRegistry-based workflows.
"""

from .api import (
    load,
    LoadOptions,
    ConceptRegistry,          
    ConceptRecord,
    ConceptGroupRecord,
    RegistryDiff,
    load_schema_info,
    RoleDefinition,
    SchemaInfo,
    BASE_DIR,
    SCHEMA_DIR,
    INSTANCE_DIR,
)

__all__ = [
    "load",
    "LoadOptions",
    "ConceptRegistry",
    "ConceptRecord",
    "ConceptGroupRecord",
    "RegistryDiff",
    "load_schema_info",
    "RoleDefinition",
    "SchemaInfo",
    "BASE_DIR",
    "SCHEMA_DIR",
    "INSTANCE_DIR",
]
