# Usage

This page shows the main loading paths that end users can rely on today.

## 1. Stable named ids for downstream code

Use `runtime.default_valuesets` when you need stable named concept ids in
downstream logic.

This is the default choice for code such as:

```python
from omop_semantics.runtime.default_valuesets import runtime

condition_episodes["episode_concept_id"] = runtime.types.disease_episode_types.episode_of_care
condition_episodes["episode_type_concept_id"] = runtime.types.source_types.ehr_defined
```

This path is appropriate when you want:

- stable named ids
- attribute-style access
- no dependency on a live OMOP vocabulary database

## 2. Templates, profiles, and profile groups

Use `OmopSemanticEngine` when you need:

- semantic templates
- compiled template views
- CDM profiles
- profile groups
- documentation or inspection of the symbolic template layer

```python
from omop_semantics.runtime import OmopSemanticEngine
from omop_semantics import INSTANCE_DIR, SCHEMA_DIR

instance_base = INSTANCE_DIR
profile_schema_base = SCHEMA_DIR / "profiles"

engine = OmopSemanticEngine.from_yaml_paths(
    registry_paths=[
        instance_base / "demographic.yaml",
    ],
    profile_paths=[
        instance_base / "profile_groups.yaml",
        profile_schema_base / "omop_staging.yaml",
        profile_schema_base / "omop_modifiers.yaml",
        profile_schema_base / "omop_episodes.yaml",
    ],
)
```

`from_yaml_paths()` accepts the shipped registry instance files directly. When a
registry file refers to a CDM profile by name such as `observation_simple`, the
engine resolves that name against the shipped `profiles.yaml` catalogue before
building the runtime registry.

Once loaded, the runtime gives you compiled template access:

```python
tpl = engine.registry_runtime.get_runtime("Country of birth")
tpl.entity_concept_ids
# {4155450}
```

This path is appropriate when you need the semantic object plus shape
combination that makes up the meaningful template layer.

Useful runtime helpers on `engine.registry_runtime` include:

- `get_runtime(name)` for an ergonomic attribute-based template view
- `by_label(label)` for case-insensitive template lookup
- `allows_concept(name, concept_id)` to test entity concept membership
- `allows_value(name, concept_id)` to test value concept membership

## 3. Fallback and default concepts

Use `omop_semantics.unknowns` when you need a standard fallback concept and a
machine-readable reason for why it was chosen.

```python
from omop_semantics.unknowns import UNKNOWN

UNKNOWN["generic"].concept_id
# 4129922

UNKNOWN["condition"].reason
# "mapping_failed"
```

This surface is useful when you want:

- a consistent fallback concept catalog across ETL jobs
- a reason code that distinguishes missing input from mapping failure
- one import path for default and unknown concepts

## 4. Lower-level loading helpers

If you need custom composition rather than the high-level engine, the
`omop_semantics.runtime` package also exports lower-level helpers:

```python
from omop_semantics.runtime import (
    load_registry_fragment,
    load_symbol_module,
    merge_registry_fragments,
)
```

Use these when you are assembling your own registry fragments or symbolic
modules explicitly. For shipped instance files, `OmopSemanticEngine.from_yaml_paths()`
is usually the better starting point because it also handles named
`cdm_profile` interpolation for you.

## 5. Template-driven ETL routing

Compiled templates can drive row-shape routing cleanly:

```python
from omop_semantics.runtime import RuntimeTemplate


def emit_row_from_template(
    tpl: RuntimeTemplate,
    *,
    concept_id: int,
    value: str | int | None,
    person_id: int,
    date: str,
) -> tuple[str, dict]:
    profile = tpl.cdm_profile

    row: dict[str, object] = {
        profile.concept_slot: concept_id,
        "person_id": person_id,
        "observation_date": date,
    }

    if profile.value_slot:
        row[profile.value_slot] = value

    return profile.cdm_table, row
```

This is the main reason to move beyond raw ids and into the template/profile
runtime.
