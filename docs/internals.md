# Internals

This page is a Phase 0 orientation guide to the current package structure.

## Repo map

At a high level, the repo reads most usefully as:

1. **Authoring layer**
   - `src/omop_semantics/schema/configuration/`
   - `src/omop_semantics/schema/instances/`

2. **Typed runtime layer**
   - `src/omop_semantics/runtime/`

3. **Compatibility layer**
   - `src/omop_semantics/utils/load.py`
   - `src/omop_semantics/schema/registry.py`
   - exports in `omop_semantics.__init__`

## Current public runtime surfaces

### Value-set runtime

Primary entrypoint:

```python
from omop_semantics.runtime.default_valuesets import runtime
```

This is a real downstream compatibility surface used by code such as:

```python
runtime.types.disease_episode_types.episode_of_care
runtime.types.source_types.ehr_defined
```

Phase 0 assumption:
this import path and attribute-style access pattern should be preserved.

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

### Older `ConceptRegistry` API

Primary entrypoints:

```python
from omop_semantics import load
from omop_semantics import ConceptRegistry
```

This remains exported and usable, but it should be understood as a compatibility
surface for older registry-oriented workflows rather than the only conceptual
center of the package.

## Why both runtime paths exist

The package currently supports two different styles of downstream usage:

1. simple stable named ids
   Best served by `runtime.default_valuesets`

2. shape-aware semantic work
   Best served by `OmopSemanticEngine`

The older `ConceptRegistry` path still exists because it remains useful for
validation and some registry-style workflows, but it is no longer sufficient by
itself to explain the full shape of the package.

## Performance and expansion boundary

`omop-semantics` itself should remain portable and fast.

That means:

- no required live vocabulary database
- no required descendant expansion at load time
- runtime artifacts are anchor-based and structural

DB-aware consumers can expand those anchors later if needed.
