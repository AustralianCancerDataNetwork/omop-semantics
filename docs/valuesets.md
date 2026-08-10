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
              ├── RuntimeEnum    — exact, fixed concept list
              ├── RuntimeGroup   — descendant-expanding anchors
              └── OmopConcept    — exact singleton
```

Access remains scoped to each level of the hierarchy. A value set exposes its
semantic-unit names, and a semantic unit exposes the labels from its constituent
groups, enums, and concepts. For example,
`runtime.staging.t_stage_concepts.t3` returns the concept id, while
`runtime.staging.t3` raises `AttributeError` because `t3` is not a semantic-unit
name.

A semantic unit can compose one group with exact enums or named concepts. This
keeps expansion semantics explicit while publishing one governed concept set:

```python
surgery = runtime.cancer_procedures.cancer_indicating_surgery
surgery.parent_ids           # anchors whose descendants are included
surgery.exact_ids            # concepts matched exactly
surgery.excluded_parent_ids  # anchors whose descendants are excluded
```

### `RuntimeGroup` singleton shortcut

A group with exactly one parent concept collapses to a plain `int` on attribute access. A group with multiple parents returns the `RuntimeGroup` object. Call `.is_singleton` to test this explicitly, or retrieve the group through `unit.groups[name]` when role-specific access is required.

### Available methods

All labelled-concept types expose label lookup and a sorted `.labels` list.
Their set accessors differ intentionally:

| Runtime type | Attribute / Method | Returns |
|---|---|---|
| `RuntimeEnum` | `.ids`, `.mapper()` | complete exact members |
| `RuntimeGroup` | `.parent_ids`, `.parent_mapper()` | descendant-expanding inclusion anchors |
| `RuntimeGroup` | `.excluded_parent_ids`, `.excluded_parent_mapper()` | descendant-expanding exclusion anchors |
| `RuntimeSemanticUnit` | `.exact_ids`, `.exact_mapper()` | enum and named-concept members matched exactly |
| `RuntimeSemanticUnit` | `.parent_ids`, `.parent_mapper()` | descendant-expanding inclusion anchors from its governed group |
| `RuntimeSemanticUnit` | `.excluded_parent_ids`, `.excluded_parent_mapper()` | descendant-expanding exclusion anchors from its governed group |

`RuntimeGroup.ids`, `RuntimeGroup.mapper()`, `RuntimeGroup.excluded_ids`, and
`RuntimeGroup.excluded_mapper()` are deprecated compatibility aliases. Group-backed
`RuntimeSemanticUnit.ids` is also deprecated because a flat set cannot preserve
parent-versus-exact expansion semantics. Enum-only semantic-unit `.ids` remains supported.

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
| `cancer_procedures` | Consult types, provider specialties, governed radiotherapy, cancer-indicating surgery, diagnostic/staging procedures, and location |
| `sact` | SACT drug inclusion and exclusion anchors |
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

Simple semantic-unit entries remain string references. To compose descendant
anchors with exact members, use a named mapping with typed reference lists:

```yaml
valuesets:
  - name: cancer_procedures
    semantic_units:
      - name: cancer_indicating_surgery
        notes: Cancer-directed surgery with exact exceptions.
        named_groups:
          - cancer_indicating_surgery_parent_concepts
        named_enumerators:
          - cancer_indicating_surgery_point_concepts
```

A composite unit may contain at most one group. Its membership is the resolved
group result union its exact enum and named-concept members. Typed references are
constituents of the named composite; they do not create additional semantic-unit
paths in that value set. Access the exact members above through
`runtime.cancer_procedures.cancer_indicating_surgery.exact_ids`.

## API reference

::: omop_semantics.runtime.value_sets.RuntimeValueSets

::: omop_semantics.runtime.value_sets.RuntimeValueSet

::: omop_semantics.runtime.value_sets.RuntimeSemanticUnit

::: omop_semantics.runtime.value_sets.RuntimeEnum

::: omop_semantics.runtime.value_sets.RuntimeGroup

::: omop_semantics.runtime.value_sets.compile_valuesets

::: omop_semantics.runtime.value_sets.interpolate_valuesets

::: omop_semantics.runtime.value_sets.index_semantic_units
