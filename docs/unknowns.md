# Fallback Concepts

Use `omop_semantics.unknowns` when a pipeline needs a canonical fallback concept
instead of an open-ended local convention.

```python
from omop_semantics.unknowns import UNKNOWN

UNKNOWN["generic"].concept_id
# 4129922

UNKNOWN["stage_edition"].reason
# "default_value"
```

Each entry combines:

- an OMOP `concept_id`
- a human-readable label
- a `reason` code that explains why the fallback was chosen

The `reason` field is intended for application behavior and auditability. It
lets downstream code distinguish cases such as missing source data,
not-recorded values, ambiguous mappings, and explicit defaults.

::: omop_semantics.unknowns
