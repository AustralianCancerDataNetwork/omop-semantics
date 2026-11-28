# Importing omop-semantics schemas

The LinkML schemas ship in the `omop-semantics` wheel, under
`omop_semantics/schema/configuration/core/`. Each has a stable id in the
`https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/` namespace.

A downstream schema imports them with the `omop_semantics:` prefix, and loads with the
package importmap. The importmap points that prefix at the installed files, so nothing
is fetched over the network and no checkout of this repository is needed.

## In a downstream schema

```yaml
id: https://example.org/my-source
name: my_source
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
```

Importable names: `omop_base`, `omop_profiles`, `omop_templates`,
`omop_semantic_registry`, `omop_named_sets`, `omop_unknowns` and `omop_links`, each as
`omop_semantics:core/<name>`.

## SchemaView

```python
from linkml_runtime.utils.schemaview import SchemaView
from omop_semantics.schema import importmap

view = SchemaView("my_source.yaml", importmap=importmap())
concept = view.get_class("Concept")
```

To open a shipped schema directly, use its installed path. The shipped schemas import
each other by relative name, so they load without an importmap:

```python
from omop_semantics.schema import schema_path

view = SchemaView(str(schema_path("omop_templates")))
```

## LinkML generators

The importmap is specific to an installation because it points at the installed
package. Write it once, then pass it to LinkML's generators:

```sh
omop-semantics importmap --output /tmp/omop-semantics-importmap.json
gen-pydantic --importmap /tmp/omop-semantics-importmap.json my_source.yaml
```
