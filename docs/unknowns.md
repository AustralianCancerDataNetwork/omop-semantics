# Fallback Concepts

`omop_semantics.unknowns` provides a catalog of canonical fallback concepts for use when a mapping cannot be completed. Each entry pairs an OMOP concept_id with a `reason` code that describes the failure mode.

```python
from omop_semantics.unknowns import UNKNOWN

UNKNOWN["generic"].concept_id   # → 4129922
UNKNOWN["generic"].label        # → "Unknown"
UNKNOWN["generic"].reason       # → "missing"
```

`UNKNOWN` is read-only. Attempting to add or replace entries raises `TypeError`.

## Reason codes

| Code | Meaning |
|---|---|
| `"missing"` | The source value was absent or null |
| `"not_recorded"` | The value exists but was not captured |
| `"not_applicable"` | The concept does not apply in this context |
| `"ambiguous"` | The source could not be resolved to a single concept |
| `"mapping_failed"` | A value was present but could not be mapped |
| `"default_value"` | An explicit default was applied in the absence of data |

## Shipped entries

| Key | Concept ID | Label | Reason |
|---|---|---|---|
| `generic` | 4129922 | Unknown | `missing` |
| `gender` | 4214687 | Gender Unknown | `missing` |
| `condition` | 44790729 | Unknown problem | `mapping_failed` |
| `cancer` | 36402660 | Unknown histology of unknown primary site | `mapping_failed` |
| `grade` | 4264626 | Grade not determined | `not_recorded` |
| `stage` | 36768646 | Cancer Modifier Origin Grade X | `not_recorded` |
| `cob` | 40482029 | Country of birth unknown | `missing` |
| `stage_edition` | 1634449 | 8th | `default_value` |
| `therapeutic_regimen` | 4207655 | prescription of therapeutic regimen | `mapping_failed` |
| `drug_trial` | 4207655 | clinical drug trial | `ambiguous` |

## Types

```python
from omop_semantics.unknowns import UnknownValue, UnknownReason
```

`UnknownValue` is a frozen dataclass with `concept_id: int`, `label: str`, and `reason: UnknownReason | None`.

`UnknownReason` is a `Literal` type alias over the six reason code strings listed above. Use it for type-safe reason-code handling in downstream code.

## Usage pattern

The `reason` field is intended to drive downstream behavior and audit trails, not just to label the concept. It distinguishes cases that look the same in the CDM but have different causes:

```python
unknown = UNKNOWN["condition"]

if unknown.reason == "missing":
    log.warning("Source value was absent")
elif unknown.reason == "mapping_failed":
    log.warning("Mapping attempt failed for present value")

row["condition_concept_id"] = unknown.concept_id
```
