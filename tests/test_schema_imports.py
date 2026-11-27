from __future__ import annotations

import json
import socket

import pytest
from linkml_runtime.utils.schemaview import SchemaView

from omop_semantics.schema import importmap, schema_path, write_importmap
from omop_semantics.schema.imports import SCHEMA_NAMES


@pytest.fixture
def no_network(monkeypatch):
    def reject_network(*args, **kwargs):
        pytest.fail("schema loading attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", reject_network)


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_shipped_schema_loads_offline_without_importmap(name, no_network):
    view = SchemaView(str(schema_path(name)))

    assert view.all_classes(imports=True)


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_downstream_schema_imports_each_shipped_schema_offline(name, tmp_path, no_network):
    # The downstream file lives outside the repo, as a consumer's schema would.
    downstream = tmp_path / "downstream.yaml"
    downstream.write_text(
        f"""id: https://example.org/downstream
name: downstream
imports:
  - linkml:types
  - omop_semantics:core/{name}
""",
        encoding="utf-8",
    )

    view = SchemaView(str(downstream), importmap=importmap())

    assert f"omop_semantics:core/{name}" in view.imports_closure()


def test_downstream_schema_uses_concept_from_omop_base(tmp_path, no_network):
    downstream = tmp_path / "downstream.yaml"
    downstream.write_text(
        """id: https://example.org/downstream
name: downstream
imports:
  - linkml:types
  - omop_semantics:core/omop_base
classes:
  SourceConcept:
    slots:
      - concept
slots:
  concept:
    range: Concept
""",
        encoding="utf-8",
    )

    view = SchemaView(str(downstream), importmap=importmap())

    assert view.get_class("Concept") is not None
    assert view.get_slot("concept").range == "Concept"


def test_schema_ids_are_unique_and_stable() -> None:
    ids = {SchemaView(str(schema_path(name))).schema.id for name in SCHEMA_NAMES}

    assert ids == {
        f"https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/{name}"
        for name in SCHEMA_NAMES
    }


def test_schema_path_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="Unknown omop-semantics schema"):
        schema_path("not_a_schema")


def test_write_importmap_writes_the_prefix_mapping(tmp_path) -> None:
    target = write_importmap(tmp_path / "importmap.json")

    assert json.loads(target.read_text(encoding="utf-8")) == importmap()
    assert set(importmap()) == {"omop_semantics:"}
