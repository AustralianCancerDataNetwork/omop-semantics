from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

# Wheels are installed as ordinary package directories.  Resolve the asset root
# through importlib.resources so paths stay anchored to the installed package.
BASE_DIR = Path(str(files("omop_semantics")))
SCHEMA_DIR = BASE_DIR / "schema" / "configuration"
INSTANCE_DIR = BASE_DIR / "schema" / "instances"


def instance_resource(name: str) -> Traversable:
    return files("omop_semantics").joinpath("schema", "instances", name)
