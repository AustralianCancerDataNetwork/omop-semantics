"""
Compatibility exports for the older registry-oriented API surface.

This module keeps the `load()` / `ConceptRegistry` style workflow available for
callers that still depend on it. New shape-aware runtime work should generally
prefer `omop_semantics.runtime`.
"""

from .utils import load, LoadOptions, BASE_DIR, SCHEMA_DIR, INSTANCE_DIR
from .schema.registry import ConceptRegistry, ConceptRecord, ConceptGroupRecord, RegistryDiff
from .schema.schema_model import load_schema_info, RoleDefinition, SchemaInfo
