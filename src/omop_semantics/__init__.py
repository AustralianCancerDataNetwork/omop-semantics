"""
Top-level exports for `omop_semantics`.

Import from the package root for:

- fallback concepts and reason codes via ``UNKNOWN``
- path helpers via ``BASE_DIR``, ``SCHEMA_DIR``, and ``INSTANCE_DIR``

For runtime access, use the dedicated subpackages:

- ``from omop_semantics.runtime.default_valuesets import runtime``
- ``from omop_semantics.runtime import OmopSemanticEngine``
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
    "main",
]


def main(argv: "list[str] | None" = None) -> int:
    """Console entry point (``omop-semantics``).

    Subcommands:
      gen-models   (re)generate the committed pydantic models from the LinkML schema.
      tui          launch the interactive output-definition explorer.
    """
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "gen-models":
        from omop_semantics.schema.codegen import cli as gen_models_cli

        return gen_models_cli(argv[1:])
    if argv and argv[0] == "tui":
        from omop_semantics.runtime.tui.app import cli as tui_cli

        return tui_cli(argv[1:])

    print("usage: omop-semantics {gen-models|tui} ...", file=sys.stderr)
    return 2
