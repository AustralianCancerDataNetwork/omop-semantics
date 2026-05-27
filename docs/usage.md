# Usage

This page describes the recommended loading paths in the current package.

## 1. Stable named ids for downstream code

Use `runtime.default_valuesets` when you need stable named concept ids in
downstream logic.

This is an active compatibility surface and should be treated as the default
choice for code such as:

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
        instance_base / "genomic.yaml",
    ],
    profile_paths=[
        instance_base / "profile_groups.yaml",
        profile_schema_base / "omop_staging.yaml",
        profile_schema_base / "omop_modifiers.yaml",
        profile_schema_base / "omop_episodes.yaml",
    ],
)
```

Once loaded, the runtime gives you compiled template access:

```python
tpl = engine.registry_runtime.get_runtime("Country of birth")
tpl.entity_concept_ids
# {4155450}
```

This path is appropriate when you need the semantic object plus shape
combination that makes up the meaningful template layer.

## 3. Older `ConceptRegistry` workflows

The package still exports the older `load()` / `ConceptRegistry` path:

```python
from omop_semantics import load

registry = load(
    schema_paths=[
        "path/to/schema_a.yaml",
        "path/to/schema_b.yaml",
    ],
    instance_paths=[
        "path/to/instances_a.yaml",
        "path/to/instances_b.yaml",
    ],
)
```

This remains useful when you specifically want the older registry model:

- concept lookup by role
- group membership queries
- schema-backed validation
- round-tripping to LinkML-compatible instance dicts

For new shape-aware work, prefer `OmopSemanticEngine`.

## 4. Template-driven ETL routing

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
