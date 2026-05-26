# omop_semantics

**omop_semantics** is a Python library for defining and managing **semantic conventions on top of OMOP CDM**.

It lets you describe conventions in code

- which OMOP concepts you want to have on hand as named key concepts to improve ergonomics in analytic code,
- how they are grouped,
- what roles they play 
- and provide profiles to render these targets uniformly into CDM tables.

The goal is to make these conventions **explicit, versioned, and reusable**, instead of being buried in code, SQL, or documentation. They are also extensible so that you can add opinionated layers on top of default specifications that may be relevant in a domain-specific context only.

---

## Current structure

The library currently has two main runtime surfaces and one older compatibility
surface:

- **Value-set runtime**
  For stable named ids and ergonomic downstream access such as
  `from omop_semantics.runtime.default_valuesets import runtime`.

- **Template/profile runtime**
  For working with semantic templates, compiled template views, and CDM row
  shapes via `OmopSemanticEngine`.

- **ConceptRegistry compatibility API**
  The older `load()` / `ConceptRegistry` path is still exported for workflows
  that rely on it, but it should be treated as a compatibility surface rather
  than the only mental model for the package.

If you are starting new downstream code today:

1. use `runtime.default_valuesets` when you need stable named concept ids,
2. use `OmopSemanticEngine` when you need templates, profiles, or profile
   groups,
3. use `load()` / `ConceptRegistry` when you specifically need the older
   registry behavior.

---

## Key ideas

- **Human-authored**  
  Semantic rules and concept groups are written in YAML and validated with schemas.

- **Portable**  
  No database or graph store required.

- **Versionable**  
  Conventions can evolve over time and be tracked in git.

- **Integrates with pipelines**  
  Can drive ETL logic, validation, and documentation so they stay in sync.

---

## Typical workflow

1. **Define a schema**  
   Describes what kinds of semantic objects and roles exist (e.g. staging,
   modifiers).

2. **Write YAML instances**  
   Lists actual OMOP concepts, profiles, and templates used in your project.

3. **Load the runtime surface you need**  
   Use value sets for named ids, or the semantic engine for template/profile
   work.

4. **Use it in code**  
   For validation, cohort logic, ETL constraints, or documentation.

---

## When should you use this?

Use **omop_semantics** if you:

- have project-specific rules about which OMOP concepts are valid,  
- need consistent concept groupings across ETL and analytics,  
- want semantic conventions to be explicit, testable, and versioned,  
- are working in domains like oncology where OMOP alone is too permissive.

---

## Docs map

- `docs/usage.md`
  Recommended loading paths for value sets, templates/profiles, and older
  registry workflows.

- `docs/data-model.md`
  The conceptual distinction between profiles, profile groups, templates, and
  semantic objects.

- `docs/schema-and-instances.md`
  Canonical authoring assets and how the shipped schema/instance files are
  organized.

- `docs/internals.md`
  Repo structure, public runtime surfaces, and compatibility notes.
