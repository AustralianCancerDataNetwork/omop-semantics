# Internals

## Package layout

```
src/omop_semantics/
├── __init__.py              # Package root: UNKNOWN, path helpers
├── unknowns.py              # Fallback concept catalog
├── base.py                  # ConceptEnum base class
├── utils/
│   └── paths.py             # BASE_DIR, SCHEMA_DIR, INSTANCE_DIR
├── runtime/
│   ├── __init__.py          # Public runtime exports
│   ├── default_valuesets.py # Eagerly loaded default runtime object
│   ├── value_sets.py        # RuntimeValueSets hierarchy and compiler
│   ├── resolver.py          # OmopSemanticEngine, OmopRegistryRuntime, resolver
│   ├── instance_loader.py   # YAML loading and profile interpolation helpers
│   ├── renderers.py         # HTML rendering helpers for notebooks
│   └── unknown_handlers.py  # Re-export shim (import from unknowns instead)
└── schema/
    ├── codegen.py           # PydanticGenerator wrapper and CLI
    ├── dump.py              # YAML dump utility
    ├── configuration/       # LinkML schemas
    ├── instances/           # Canonical YAML instance files
    └── generated_models/    # Committed generated Pydantic models
```

## Public surfaces

### Package root

```python
from omop_semantics import UNKNOWN, UnknownValue, UnknownReason
from omop_semantics import BASE_DIR, SCHEMA_DIR, INSTANCE_DIR
```

`BASE_DIR` points to `src/omop_semantics/`. `SCHEMA_DIR` and `INSTANCE_DIR` point to the `configuration/` and `instances/` subdirectories.

### Value-set runtime

```python
from omop_semantics.runtime.default_valuesets import runtime
```

`default_valuesets` loads and compiles the full value-set registry eagerly at import time. If the YAML files are missing or malformed, the error surfaces at import.

The object hierarchy is:

```
RuntimeValueSets          ← runtime
  └── RuntimeValueSet     ← runtime.staging
        └── RuntimeSemanticUnit   ← runtime.staging.t_stage_concepts
              ├── RuntimeEnum     ← wraps OmopEnum
              └── RuntimeGroup    ← wraps OmopGroup
```

Attribute access at any level falls through to the underlying concept ids: `runtime.staging.t3` and `runtime.staging.t_stage_concepts.t3` both work. `__dir__` is implemented on all levels to support tab-completion.

### Template/profile runtime

```python
from omop_semantics.runtime import OmopSemanticEngine
```

`OmopSemanticEngine` wires together:

- `OmopSemanticResolver` — resolves `OmopConcept / OmopGroup / OmopEnum / OmopValueSet` → `set[int]`
- `OmopTemplateRuntime` — compiles a single `OmopTemplate` into a `CompiledTemplate`
- `OmopRegistryRuntime` — indexed access to compiled templates with caching
- `SemanticProfileRuntime` — optional symbolic view of profile objects for inspection and documentation

### Lower-level helpers

```python
from omop_semantics.runtime import (
    load_registry_fragment,
    merge_registry_fragments,
    load_symbol_module,
)
```

These are exposed for cases where you want to assemble registry fragments manually. They are also used internally by `from_yaml_paths()`.

## What `from_yaml_paths()` does

1. Loads the CDM profile catalogue from `profiles.yaml` (or the custom `profiles_path` if provided).
2. For each registry file, checks whether any template uses a string-named `cdm_profile`. If so, expands those names against the catalogue, then validates the result as a `RegistryFragment`. Files with fully-expanded profiles are loaded directly.
3. Merges all fragments into a single `RegistryFragment`.
4. Loads any `profile_paths` files as raw symbol dictionaries (no schema validation) and stores them in `SemanticProfileRuntime`.

## Compilation and caching

`OmopRegistryRuntime` compiles templates lazily on first access. The compiled index (`_compiled_by_name` and `_compiled_by_role`) is computed once and cached. Subsequent calls to `get()`, `by_role()`, `compile_all()`, and similar methods use the cache.

To compile explicitly:

```python
engine.registry_runtime.compile_index()
```

## Registry diff and merge

Two `OmopRegistryRuntime` instances can be compared:

```python
diff = engine_a.registry_runtime.diff(engine_b.registry_runtime)
diff.added_templates    # templates in b but not a
diff.removed_templates  # templates in a but not b
diff.changed_templates  # templates in both but with different compiled output
diff.is_empty           # True if the registries are semantically identical
```

They can also be merged:

```python
merged = engine_a.registry_runtime.merge(
    engine_b.registry_runtime,
    strategy="prefer_other",  # or "prefer_self" (default) or "error"
)
```

The merged result flattens both registries into a single group. Original group structure is not preserved.

## CLI

```bash
omop-semantics gen-models           # regenerate committed Pydantic models
omop-semantics gen-models --check   # exit 1 if models are out of sync
omop-semantics gen-models --out DIR # write to a custom directory
```

The generator uses `linkml.generators.pydanticgen.PydanticGenerator` with options pinned in `schema/codegen.py`. Run it using the project's own virtual environment to ensure the correct `linkml` version is used.

## Portability

The library requires no live vocabulary database and performs no descendant expansion at load time. The `OmopGroup` semantic is: "the set of descendants of these anchor concepts." The anchor ids are stored and returned; expansion is the consumer's responsibility.

HTML rendering (`_repr_html_`) is implemented on all major runtime types for notebook use. `h()` in `renderers.py` escapes all user-controlled content before inserting it into HTML.
