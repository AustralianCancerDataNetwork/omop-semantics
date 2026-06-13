# Value Sets

The value-set runtime gives you stable named concept ids with attribute-style access. It is the right choice for application logic, ETL constants, and validation rules where you want a consistent named import rather than a hardcoded integer.

```python
from omop_semantics.runtime.default_valuesets import runtime

runtime.types.disease_episode_types.episode_of_care  # → 32533
runtime.staging.t_stage_concepts.t3                  # → 1634376
runtime.genomic.genomic_value_group.genomic_positive  # → 9191
```

## Object hierarchy

The runtime is a four-level namespace:

```
RuntimeValueSets (runtime)
  └── RuntimeValueSet (runtime.staging)
        └── RuntimeSemanticUnit (runtime.staging.t_stage_concepts)
              ├── RuntimeEnum    — fixed concept list
              └── RuntimeGroup   — anchor-concept-based group
```

Access works at any level. `runtime.staging.t3` and `runtime.staging.t_stage_concepts.t3` both return the same concept id — the lookup falls through from the value set to its units and their members.

### `RuntimeGroup` singleton shortcut

A group with exactly one parent concept collapses to a plain `int` on attribute access. A group with multiple parents returns the `RuntimeGroup` object. Call `.is_singleton` to test this explicitly, or use `.ids` to always get a `set[int]` regardless.

### Available methods

All labelled-concept types (`RuntimeEnum`, `RuntimeGroup`) expose:

| Attribute / Method | Returns |
|---|---|
| `.<label>` | `int` concept_id |
| `.ids` | `set[int]` of all concept ids |
| `.labels` | sorted `list[str]` of labels |
| `.mapper()` | `dict[str, int]` label → concept_id |

`RuntimeSemanticUnit` additionally exposes `.enums`, `.groups`, and `.concepts` as dictionaries for direct access to the underlying objects.

## What value sets are available

The shipped value sets are defined in `instances/valuesets.yaml`. Current top-level names:

| Name | Contents |
|---|---|
| `genomic` | Genomic result values and mapped gene types |
| `modifiers` | Modifier fields and tables |
| `types` | Episode types and source types |
| `treatment_modifiers` | Treatment intent, modality, and modifier values |
| `condition_modifiers` | Condition modifier values, tumour grade, numeric modifiers, condition status |
| `nlp` | Document type, encoding, and language |
| `cancer_procedures` | Consult types, provider specialties, procedure types, location |
| `measurements_numeric` | Body size units and measurements, lab values, smoking, PROMs, performance status |
| `staging` | T, N, M, and group stage concepts plus stage edition |
| `visits` | Visit modalities |
| `observations` | Demography and SACT concepts |
| `unknowns` | Canonical unknown/fallback concepts |

## Loading your own value sets

The default `runtime` object loads the shipped enumerators and value sets at import time. To load a custom set instead, use the compiler directly:

```python
from linkml_runtime.loaders import yaml_loader
from omop_semantics.schema.generated_models.omop_named_sets import CDMSemanticUnits
from omop_semantics.runtime.value_sets import (
    index_semantic_units,
    interpolate_valuesets,
    compile_valuesets,
)
from omop_semantics import INSTANCE_DIR

enumerators = yaml_loader.load(
    str(INSTANCE_DIR / "enumerators.yaml"),
    target_class=CDMSemanticUnits,
)
idx = index_semantic_units(enumerators)
value_sets = yaml_loader.load_as_dict(str(INSTANCE_DIR / "valuesets.yaml"))
value_set_objects = interpolate_valuesets(value_sets, idx)
runtime = compile_valuesets(value_set_objects)
```

Substitute your own YAML file paths to load project-specific value sets or extend the shipped ones.

## API reference

::: omop_semantics.runtime.value_sets.RuntimeValueSets

::: omop_semantics.runtime.value_sets.RuntimeValueSet

::: omop_semantics.runtime.value_sets.RuntimeSemanticUnit

::: omop_semantics.runtime.value_sets.RuntimeEnum

::: omop_semantics.runtime.value_sets.RuntimeGroup

::: omop_semantics.runtime.value_sets.compile_valuesets

::: omop_semantics.runtime.value_sets.interpolate_valuesets

::: omop_semantics.runtime.value_sets.index_semantic_units
