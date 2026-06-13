# Registry Runtime

The registry runtime compiles declarative semantic templates into execution-ready objects. It is the layer between YAML authoring and ETL/analytics code.

The primary entrypoint is `OmopSemanticEngine`. Everything else on this page is accessible through it.

## Quick example

```python
from omop_semantics.runtime import OmopSemanticEngine
from omop_semantics import INSTANCE_DIR, SCHEMA_DIR

engine = OmopSemanticEngine.from_yaml_paths(
    registry_paths=[INSTANCE_DIR / "demographic.yaml"],
    profile_paths=[INSTANCE_DIR / "profile_groups.yaml"],
)

# Compiled template access
tpl = engine.registry_runtime.get_runtime("Language spoken")
tpl.cdm_profile.cdm_table     # → "observation"
tpl.cdm_profile.value_slot    # → "value_as_concept_id"
tpl.entity_concept_ids        # → {4052785}
tpl.value_concept_ids         # → {4182347}

# Membership tests
engine.registry_runtime.allows_concept("Language spoken", 4052785)  # → True
engine.registry_runtime.allows_value("Language spoken", 4182347)    # → True

# Iterate by role
for tpl in engine.registry_runtime.by_role_runtime("demographic"):
    print(tpl.name, tpl.cdm_profile.cdm_table)
```

## Class responsibilities

**`OmopSemanticEngine`** is the entry point. It owns the resolver, compiler, and registry runtime as attributes. Use `from_yaml_paths()` for shipped YAML files or `from_instances()` for programmatic fragment construction.

**`OmopRegistryRuntime`** provides indexed, compiled access to a `RegistryFragment`. It compiles on first access and caches the result. Also provides `diff()` and `merge()` for comparing and combining registries.

**`OmopSemanticResolver`** turns a semantic object (`OmopConcept`, `OmopGroup`, `OmopEnum`, `OmopValueSet`) into a `set[int]`. Each type has a specific resolution:
- `OmopConcept` → `{concept_id}`
- `OmopEnum` → set of all member concept_ids
- `OmopGroup` → set of all anchor (`parent_concepts`) concept_ids
- `OmopValueSet` → union of its members' resolved sets

**`OmopTemplateRuntime`** compiles a single `OmopTemplate` into a `CompiledTemplate` (TypedDict) by invoking the resolver on its `entity_concept` and `value_concept`.

**`RuntimeTemplate`** is an attribute-based view over a `CompiledTemplate`. Access `tpl.name`, `tpl.role`, `tpl.cdm_profile`, `tpl.entity_concept_ids`, `tpl.value_concept_ids` directly.

**`SemanticProfileRuntime`** provides read-only access to raw profile object dictionaries loaded from symbolic YAML files. Used for documentation and inspection, not for ETL execution. Available via `engine.profile_runtime` when `profile_paths` are provided.

## API reference

::: omop_semantics.runtime.OmopSemanticEngine

::: omop_semantics.runtime.OmopRegistryRuntime

::: omop_semantics.runtime.RuntimeTemplate

::: omop_semantics.runtime.OmopTemplateRuntime

::: omop_semantics.runtime.OmopSemanticResolver

::: omop_semantics.runtime.SemanticProfileRuntime
