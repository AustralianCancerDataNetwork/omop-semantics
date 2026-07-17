"""
Public runtime exports for `omop_semantics`.

Use this package when you need compiled templates, profile inspection, or
low-level YAML loading helpers. For the default named-id surface, import
``runtime`` from ``omop_semantics.runtime.default_valuesets``.
"""

from .instance_loader import load_registry_fragment, merge_registry_fragments, load_symbol_module
from .renderers import render_registry_fragment, render_profile_groups, Html
from .resolver import (
    OmopSemanticResolver,
    OmopTemplateRuntime,
    OmopRegistryRuntime,
    OmopCdmProfile,
    RegistryFragment,
    OmopTemplate,
    RuntimeTemplate,
    OmopSemanticEngine,
    OmopSemanticObject,
    SemanticProfileRuntime
)
from .projection import (
    ProjectionProfileRuntime,
    RuntimeProjectionProfile,
    ProjectedOutputRow,
    ProjectedOutputLink,
    ProjectedOutputBundle,
)
from .output_definitions import (
    ContextFieldRef,
    OutputRowProjection,
    OutputLinkRule,
    OutputDefinition,
    CompiledOutputDefinition,
    OutputDefinitionRuntime,
)
from typing import TYPE_CHECKING


__all__ = [
    "OmopSemanticResolver",
    "OmopTemplateRuntime",
    "OmopRegistryRuntime",
    "OmopCdmProfile",
    "RegistryFragment",
    "OmopTemplate",
    "RuntimeTemplate",
    "OmopSemanticEngine",
    "OmopSemanticObject",
    "load_registry_fragment",
    "merge_registry_fragments",
    "load_symbol_module",
    "render_registry_fragment",
    "render_profile_groups",
    "SemanticProfileRuntime",
    "ProjectionProfileRuntime",
    "RuntimeProjectionProfile",
    "ProjectedOutputRow",
    "ProjectedOutputLink",
    "ProjectedOutputBundle",
    "ContextFieldRef",
    "OutputRowProjection",
    "OutputLinkRule",
    "OutputDefinition",
    "CompiledOutputDefinition",
    "OutputDefinitionRuntime",
]
