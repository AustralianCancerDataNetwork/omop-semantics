# omop-semantics

**omop-semantics** is a Python library for defining and managing **semantic conventions on top of OMOP CDM**.

It gives you a structured, versioned, portable layer for describing which OMOP concepts are valid in a given context, how they map to CDM row shapes, and what fallback concepts to use when a mapping cannot be completed. Conventions are authored in YAML, validated against schemas, and exposed as typed Python objects — not scattered across ETL code, SQL, or documentation.

---

## Three runtime surfaces

- **Value-set runtime**  
  Stable named concept ids for application logic:  
  `from omop_semantics.runtime.default_valuesets import runtime`

- **Template/profile runtime**  
  Compiled semantic templates and CDM profiles via `OmopSemanticEngine`.

- **Fallback concepts**  
  Canonical unknown and default concepts with reason codes:  
  `from omop_semantics.unknowns import UNKNOWN`

---

## Key properties

- **Portable** — no database or vocabulary graph required
- **Versionable** — conventions are tracked in git alongside code
- **Extensible** — add project-specific definitions on top of the shipped ones
- **Integrates with pipelines** — drives ETL logic, validation, and documentation from a single source

---

## When to use this

Use **omop-semantics** if you:

- have project-specific rules about which OMOP concepts are valid,
- need consistent concept groupings across ETL and analytics,
- want semantic conventions to be explicit, testable, and versioned,
- are working in domains like oncology where OMOP alone is too permissive.

---

## Docs

- [Usage](docs/usage.md) — loading paths and code patterns
- [Data Model](docs/data-model.md) — profiles, templates, and semantic objects
- [Schema & Instances](docs/schema-and-instances.md) — authoring assets and file organisation
- [Fallback Concepts](docs/unknowns.md) — the shipped unknown and default concepts
- [Internals](docs/internals.md) — package structure and load-time behaviour

---

## Model Visualisation

Launch the projection-visualisation notebook in Binder:

[![Launch Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/AustralianCancerDataNetwork/omop-semantics/main?labpath=examples%2Fvisualize_projection.ipynb)
