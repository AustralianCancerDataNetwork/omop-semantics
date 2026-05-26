"""
Primary typed runtime exports for templates, profiles, and semantic inspection.

The `runtime` package is the preferred entrypoint for shape-aware semantics
work. The most commonly used downstream compatibility surface for stable named
ids remains `omop_semantics.runtime.default_valuesets`.
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
]
