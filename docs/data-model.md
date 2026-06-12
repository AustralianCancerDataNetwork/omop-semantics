# Data Model

This page captures the main conceptual distinctions in the current library.

## The important distinction

Three different things are easy to blur together:

1. **Semantic object**
   What kind of OMOP thing are we talking about?
   Examples:
   - `OmopConcept`
   - `OmopGroup`
   - `OmopEnum`

2. **Profile**
   What generic OMOP row shape are we using?
   Examples:
   - `observation_simple`
   - `observation_coded`
   - `measurement_numeric`

   A profile is structural. By itself it is not yet a full semantic mapping
   unit.

3. **Template**
   A template is the semantic object plus the profile becoming the meaningful
   mapping unit.

   In practice this means:
   - a role
   - an entity concept scope
   - an optional value concept scope
   - a CDM profile

## Profile groups

Profile groups represent **admissible families of row shapes**.

Examples from the shipped instance file:

- `ObservationProfiles`
- `MeasurementProfiles`
- `ProcedureProfiles`
- `ConditionProfiles`
- `DrugExposureProfiles`

These are broader than individual templates:

- a profile says what a row looks like
- a profile group says which row shapes are valid in a family
- a template says which semantic task uses one of those shapes

## Registry groups versus profile groups

There are multiple meanings of "group" in the codebase:

- `OmopGroup`
  Semantic grouping of OMOP concepts. In the runtime layer, this resolves to
  the group's anchor `parent_concepts`.

- `RegistryGroup`
  Organizational grouping of templates in a registry fragment.

- Profile group
  A named family of admissible CDM profiles such as
  `ObservationProfiles` or `MeasurementProfiles`.

## Portable versus DB-expanded semantics

`omop-semantics` itself is intended to remain portable.

That means the runtime artifacts published here should be thought of as:

- anchor ids
- named semantic scopes
- row-shape constraints

They are **not** the same thing as a DB-expanded descendant set from a live OMOP
vocabulary graph.

If you need descendant expansion, do that in a downstream DB-aware layer after
loading these anchor-based semantics.
