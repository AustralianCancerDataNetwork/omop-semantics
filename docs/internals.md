# Internals

This page explains how the package is organized and where each public surface
lives.

## Repo map

At a high level, the repo reads most usefully as:

1. **Authoring layer**
   - `src/omop_semantics/schema/configuration/`
   - `src/omop_semantics/schema/instances/`

2. **Typed runtime layer**
   - `src/omop_semantics/runtime/`

3. **Fallback concepts**
   - `src/omop_semantics/unknowns.py`

4. **Path helpers and CLI**
   - `src/omop_semantics/utils/paths.py`
   - `omop_semantics:main`

## Current public runtime surfaces

### Value-set runtime

Primary entrypoint:

```python
from omop_semantics.runtime.default_valuesets import runtime
```

Use this when you want stable named ids in downstream code:

```python
runtime.types.disease_episode_types.episode_of_care
runtime.types.source_types.ehr_defined
```

### Template/profile runtime

Primary entrypoint:

```python
from omop_semantics.runtime import OmopSemanticEngine
```

Use this when you need:

- templates
- compiled template views
- profiles
- profile groups
- shape-aware documentation or validation logic

### Fallback concepts

Primary entrypoints:

```python
from omop_semantics.unknowns import UNKNOWN
from omop_semantics.unknowns import UnknownValue
```

Use this when you need canonical unknown/default concepts and a reason code that
explains why the fallback was chosen.

## Lower-level helpers

The `omop_semantics.runtime` package also exports lower-level helpers for custom
assembly:

```python
from omop_semantics.runtime import (
    load_registry_fragment,
    load_symbol_module,
    merge_registry_fragments,
)
```

These are useful when you are composing registry fragments yourself rather than
starting from `OmopSemanticEngine.from_yaml_paths()`.

## What `from_yaml_paths()` does

`OmopSemanticEngine.from_yaml_paths()` is the most practical entrypoint for the
shipped YAML assets:

1. It tries to load each registry file directly as a `RegistryFragment`.
2. If a registry file refers to `cdm_profile` by name, it expands that name
   from `INSTANCE_DIR / "profiles.yaml"` before validating.
3. It merges all registry fragments into one runtime registry.
4. It loads any symbolic profile files you pass in as `profile_runtime`.

This is why examples that use the built-in registry files should usually start
with `from_yaml_paths()` rather than `load_registry_fragment()`.

## Portability boundary

`omop-semantics` itself should remain portable and fast.

That means:

- no required live vocabulary database
- no required descendant expansion at load time
- runtime artifacts are anchor-based and structural

If you need descendant expansion or vocabulary-graph traversal, do that in the
consumer layer after loading the registry.
