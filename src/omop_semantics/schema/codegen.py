"""In-code generation of the committed pydantic models from the LinkML schema.

Replaces the removed ``runtime/utils.py::generate_pydantic_from_linkml`` (which shelled out to
``uv run gen-pydantic``). Uses the LinkML :class:`PydanticGenerator` API directly, so the generation
options live in code (single source of truth) and the output is reproducible against the pinned
linkml version - no remembered CLI flags.

CLI (wired via ``omop-semantics`` console script)::

    omop-semantics gen-models           # (re)write the committed modules
    omop-semantics gen-models --check   # exit non-zero if committed models are stale
    omop-semantics gen-models --out DIR # write elsewhere (e.g. a temp dir)
"""
from __future__ import annotations

import argparse
import os
import sys
from contextlib import contextmanager
from pathlib import Path

from linkml.generators.pydanticgen import PydanticGenerator

from omop_semantics.utils.paths import BASE_DIR

# Repo root (.../omop-semantics). Generation runs with cwd here and passes repo-root-relative schema
# paths, so the ``source_file`` stamp baked into each module is portable (not machine-specific).
REPO_ROOT = BASE_DIR.parent.parent
GENERATED_DIR = BASE_DIR / "schema" / "generated_models"

# Empty-list-for-multivalued behaviour.
#   False -> linkml >=1.11 default: optional multivalued slots default to ``None``.
#   True  -> pre-1.11 style: default ``[]`` plus a ``treat_empty_lists_as_none`` serializer.
# The runtime reads these collections defensively (``x or []``), so ``None`` is safe; we adopt the
# current toolchain default. Change in ONE place if the project ever wants the old style back.
EMPTY_LIST_FOR_MULTIVALUED = False

# Generated module -> source schema, as paths RELATIVE TO REPO_ROOT.
# ``omop_semantic_registry`` is the primary runtime module: its schema imports the full tree
# (registry -> core/omop_templates -> omop_base + omop_profiles), so one regen covers all of them.
# ``template_set`` is intentionally excluded: it is imported nowhere (vestigial).
GEN_TARGETS: dict[str, str] = {
    "omop_semantic_registry": "src/omop_semantics/schema/configuration/registry/omop_semantic_registry.yaml",
    "omop_named_sets": "src/omop_semantics/schema/configuration/core/omop_named_sets.yaml",
}


@contextmanager
def _chdir(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def render_module(schema_rel: str) -> str:
    """Return the generated pydantic module source for one schema (path relative to REPO_ROOT)."""
    with _chdir(REPO_ROOT):
        return PydanticGenerator(
            schema_rel,
            empty_list_for_multivalued_slots=EMPTY_LIST_FOR_MULTIVALUED,
        ).serialize()


def generate_models(out_dir: Path | None = None) -> list[Path]:
    """Generate every committed pydantic module. Returns the written paths."""
    target_dir = out_dir or GENERATED_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for module, schema_rel in GEN_TARGETS.items():
        path = target_dir / f"{module}.py"
        path.write_text(render_module(schema_rel))
        written.append(path)
    return written


def check_models() -> list[str]:
    """Return the names of any committed modules that differ from a fresh generation."""
    return [
        module
        for module, schema_rel in GEN_TARGETS.items()
        if (GENERATED_DIR / f"{module}.py").read_text() != render_module(schema_rel)
    ]


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omop-semantics gen-models",
        description="Generate the committed pydantic models from the LinkML schema.",
    )
    parser.add_argument("--out", type=Path, default=None,
                        help="Output directory (default: the committed generated_models dir).")
    parser.add_argument("--check", action="store_true",
                        help="Do not write; exit 1 if committed models differ from a fresh generation.")
    args = parser.parse_args(argv)

    if args.check:
        drift = check_models()
        for module in drift:
            print(f"DRIFT: {module}.py is out of sync - run `omop-semantics gen-models`", file=sys.stderr)
        return 1 if drift else 0

    for path in generate_models(args.out):
        print(f"wrote {path}")
    return 0
