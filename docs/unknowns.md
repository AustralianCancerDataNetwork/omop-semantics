# Fallback Concepts

`omop_semantics.unknowns` loads a small catalogue of behavioural fallbacks. The identifiers and reasons live in `schema/instances/unknowns.yaml` and are validated against `schema/configuration/core/omop_unknowns.yaml`.

These entries are deliberately separate from the value-set runtime: `reason` records why a fallback was selected, not membership in an OMOP value set.

```python
from omop_semantics.unknowns import UNKNOWN

UNKNOWN["generic"].concept_id  # → 4129922
UNKNOWN["cob"].reason          # → "missing"
```

## Catalogue

| Key | Concept ID | Reason |
|---|---:|---|
| `generic` | 4129922 | `missing` |
| `cob` | 40482029 | `missing` |
| `therapeutic_regimen` | 4207655 | `mapping_failed` |

`UNKNOWN` is read-only. Each `UnknownValue` is a frozen dataclass with `concept_id`, `label` (the key), and a required `reason`.

## Reasons

| Reason | Meaning |
|---|---|
| `missing` | The source value was absent. |
| `mapping_failed` | A source value was present but could not be mapped. |

The `UnknownReason` enum is generated from the catalogue schema and re-exported from `omop_semantics.unknowns`.
