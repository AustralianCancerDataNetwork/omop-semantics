# omop-semantics

**omop-semantics** is a Python library for defining and managing **semantic conventions on top of OMOP CDM**.

It gives you a structured, versioned, portable layer for describing which OMOP concepts are valid in a given context, how they map to CDM row shapes, and what fallback concepts to use when a mapping cannot be completed. Conventions are authored in YAML, validated against schemas, and exposed as typed Python objects — not scattered across ETL code, SQL, or documentation.

---

## Runtime contract owners

| Contract | Public API |
| --- | --- |
| Named concepts and value sets | `omop_semantics.runtime.default_valuesets.runtime` |
| Compiled semantic templates and CDM profiles | `omop_semantics.runtime.OmopSemanticEngine` |
| Fallback concepts and reason codes | `omop_semantics.unknowns` |
| CDM 5.4.2 event-field links | `omop_semantics.links` exports `LINK_MECHANISMS`, `LinkMechanism`, and `field_concept_id` |

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
