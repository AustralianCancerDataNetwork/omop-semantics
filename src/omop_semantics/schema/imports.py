"""Offline import helpers for LinkML schemas shipped with omop-semantics."""

from __future__ import annotations

import argparse
import json
from importlib.resources import files
from pathlib import Path

IMPORT_PREFIX = "omop_semantics:"
"""Prefix a downstream schema uses to import a shipped schema, e.g. ``omop_semantics:core/omop_base``."""

SCHEMA_NAMES = (
    "omop_base",
    "omop_profiles",
    "omop_templates",
    "omop_semantic_registry",
    "omop_named_sets",
    "omop_unknowns",
    "omop_links",
)


def _schema_root() -> Path:
    return Path(str(files("omop_semantics").joinpath("schema", "configuration")))


def schema_path(name: str) -> Path:
    """Return the installed YAML path for a schema name, e.g. ``"omop_base"``."""
    key = name.removeprefix(IMPORT_PREFIX).removeprefix("core/").removesuffix(".yaml")
    if key not in SCHEMA_NAMES:
        choices = ", ".join(SCHEMA_NAMES)
        raise ValueError(f"Unknown omop-semantics schema {name!r}; choose one of: {choices}")
    return _schema_root() / "core" / f"{key}.yaml"


def importmap() -> dict[str, str]:
    """Return a LinkML importmap that resolves ``omop_semantics:core/<name>`` to the installed files.

    The single prefix entry maps the import prefix to the installed schema folder,
    so nested imports inside the shipped schemas resolve locally too. LinkML
    handles ``linkml:types`` from its own installation. Nothing is fetched over
    the network.
    """
    return {IMPORT_PREFIX: f"{_schema_root()}/"}


def write_importmap(path: str | Path) -> Path:
    """Write the current installation's importmap as JSON for LinkML generators."""
    target = Path(path)
    target.write_text(json.dumps(importmap(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omop-semantics importmap")
    parser.add_argument("--output", required=True, type=Path, help="JSON file to write")
    args = parser.parse_args(argv)
    print(write_importmap(args.output))
    return 0
