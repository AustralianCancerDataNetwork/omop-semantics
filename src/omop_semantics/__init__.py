"""
Package exports for omop-semantics.

Public surfaces
---------------
omop_semantics.unknowns
    Canonical fallback/default concepts with reason codes. Stable public API.
    ``from omop_semantics.unknowns import UNKNOWN``

omop_semantics.runtime
    Value-set runtime, template-registry runtime, and the OmopSemanticEngine.
    ``from omop_semantics.runtime.default_valuesets import runtime``
    ``from omop_semantics.runtime import OmopSemanticEngine``
"""

from .unknowns import UNKNOWN, UnknownValue, UnknownReason
from .utils.paths import BASE_DIR, SCHEMA_DIR, INSTANCE_DIR

__all__ = [
    # unknowns — stable public surface
    "UNKNOWN",
    "UnknownValue",
    "UnknownReason",
    # path helpers
    "BASE_DIR",
    "SCHEMA_DIR",
    "INSTANCE_DIR",
]
