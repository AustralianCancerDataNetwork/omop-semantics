# Usage

## 1. Stable named concept ids

Use `runtime.default_valuesets` when you need stable named concept ids in downstream logic.

```python
from omop_semantics.runtime.default_valuesets import runtime

condition_episodes["episode_concept_id"] = runtime.types.disease_episode_types.episode_of_care
condition_episodes["episode_type_concept_id"] = runtime.types.source_types.ehr_defined
```

The `runtime` object is a read-only namespace. Top-level attributes correspond to named value sets (`runtime.genomic`, `runtime.staging`, `runtime.types`, etc.). Within each, semantic units are accessible by name, and their members by label.

```python
runtime.staging.t_stage_concepts.t3          # → int concept_id
runtime.staging.t_stage_concepts.ids          # → set[int] of all T-stage ids
runtime.staging.t_stage_concepts.labels       # → sorted list of label strings
```

Singleton groups collapse to a plain int automatically; multi-member groups return a `RuntimeGroup` with `.ids`, `.labels`, and `.mapper()`.

This surface requires no database and no vocabulary graph. It is the right choice when you want consistent named imports for application logic, validation rules, or generated documentation.

## 2. Templates, profiles, and profile groups

Use `OmopSemanticEngine` when you need compiled semantic templates, CDM profiles, or profile groups.

```python
from omop_semantics.runtime import OmopSemanticEngine
from omop_semantics import INSTANCE_DIR, SCHEMA_DIR

engine = OmopSemanticEngine.from_yaml_paths(
    registry_paths=[
        INSTANCE_DIR / "demographic.yaml",
    ],
    profile_paths=[
        INSTANCE_DIR / "profile_groups.yaml",
        SCHEMA_DIR / "profiles" / "omop_staging.yaml",
        SCHEMA_DIR / "profiles" / "omop_modifiers.yaml",
        SCHEMA_DIR / "profiles" / "omop_episodes.yaml",
    ],
)
```

Registry files that reference CDM profiles by name (e.g. `cdm_profile: observation_simple`) are resolved automatically against the shipped `profiles.yaml` catalogue.

To use a custom profile catalogue instead of the shipped one, pass `profiles_path`:

```python
engine = OmopSemanticEngine.from_yaml_paths(
    registry_paths=[INSTANCE_DIR / "demographic.yaml"],
    profiles_path=Path("my_project/profiles.yaml"),
)
```

### Compiled template access

```python
tpl = engine.registry_runtime.get_runtime("Country of birth")
tpl.role                  # → "demographic"
tpl.cdm_profile.name      # → "observation_simple"
tpl.cdm_profile.cdm_table # → "observation"
tpl.entity_concept_ids    # → {4155450}
tpl.value_concept_ids     # → None
```

Other useful methods on `engine.registry_runtime`:

| Method | Purpose |
|---|---|
| `get_runtime(name)` | Retrieve a compiled template by exact name |
| `by_label(label)` | Case-insensitive name lookup |
| `by_role_runtime(role)` | All compiled templates for a role |
| `allows_concept(name, concept_id)` | Test whether a concept_id is in the entity slot |
| `allows_value(name, concept_id)` | Test whether a concept_id is in the value slot |
| `roles` | Set of all role strings in the registry |
| `template_names` | Set of all template names in the registry |
| `validate()` | Check for duplicate names and missing entity concepts |

### Profile group access

Profile groups are available when profile files are passed to `profile_paths`:

```python
groups = engine.profile_runtime.list_groups()
# → {"ObservationProfiles": {"members": ["observation_simple", ...]}, ...}
```

### ETL routing

Compiled templates carry enough information to route row construction without additional lookup:

```python
from omop_semantics.runtime import RuntimeTemplate


def build_row(tpl: RuntimeTemplate, *, concept_id: int, value=None, person_id: int, date: str) -> tuple[str, dict]:
    profile = tpl.cdm_profile
    row: dict = {
        "person_id": person_id,
        profile.concept_slot: concept_id,
        f"{profile.cdm_table}_date": date,
    }
    if profile.value_slot and value is not None:
        row[profile.value_slot] = value
    return profile.cdm_table, row
```

To iterate all templates for a role:

```python
for tpl in engine.registry_runtime.by_role_runtime("demographic"):
    table, row = build_row(tpl, concept_id=..., person_id=..., date=...)
```

## 3. Fallback and default concepts

Use `omop_semantics.unknowns` when a pipeline needs a canonical fallback concept with a machine-readable reason code.

```python
from omop_semantics.unknowns import UNKNOWN

UNKNOWN["generic"].concept_id   # → 4129922
UNKNOWN["condition"].reason     # → "mapping_failed"
```

`UNKNOWN` is read-only. See [Fallback Concepts](unknowns.md) for the full catalog.

## 4. Lower-level loading helpers

If you need to assemble registry fragments manually rather than using the engine, the lower-level helpers are available:

```python
from omop_semantics.runtime import (
    load_registry_fragment,
    merge_registry_fragments,
    load_symbol_module,
)
```

`load_registry_fragment(path)` loads a single YAML file as a `RegistryFragment`. Use this when your file already has fully-expanded `OmopCdmProfile` objects rather than string profile names. `merge_registry_fragments(fragments)` combines a list of fragments into one.

For most cases, `OmopSemanticEngine.from_yaml_paths()` is the better starting point because it handles named profile resolution for you.
