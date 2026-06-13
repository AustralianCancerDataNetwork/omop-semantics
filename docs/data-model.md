# Data Model

## Semantic primitives

A **semantic primitive** describes what kind of OMOP thing something is, without saying anything about which CDM table it goes in.

There are four:

**`OmopConcept`**  
A single OMOP concept_id. Use this when exactly one concept is valid for a slot.

**`OmopGroup`**  
A named set of OMOP concepts defined by their relationship to one or more anchor (`parent_concepts`) concepts. The group's meaning is: "any standard descendant of these anchors." The library itself does not expand descendants — that belongs in a downstream database-aware layer. What the library stores and resolves are the anchor ids.

**`OmopEnum`**  
An explicitly listed, static set of concepts. Use this for short, stable lists that should not change dynamically with vocabulary updates (e.g. the T/N/M staging axes, episode type codes).

**`OmopValueSet`**  
A composite of the above. Use this when a template slot accepts concepts from multiple groups or enums — for example, a staging template whose entity could be T-stage, N-stage, or group-stage concepts.

At runtime, all four resolve to `set[int]` via `OmopSemanticResolver.resolve()`.

## Templates

A **template** binds a semantic primitive to a CDM row shape. It has:

- a **role** (e.g. `"demographic"`, `"staging"`, `"modifier"`)
- an **entity_concept** — the semantic primitive defining valid values for the CDM concept slot
- an optional **value_concept** — the semantic primitive defining valid values for the value slot
- a **cdm_profile** — the CDM row shape (see below)

Templates are the primary unit of semantic convention. A template says: "the 'Country of birth' demographic observation lives in the `observation` table, uses `observation_concept_id` for the concept, and the valid concept is `{4155450}`."

## CDM profiles

A **profile** describes the shape of a CDM row without making any semantic claim. It names:

- the target CDM table
- the concept slot (e.g. `observation_concept_id`)
- optionally, the value slot (e.g. `value_as_concept_id`, `value_as_string`, `value_as_number`)

Shipped profiles include `observation_simple`, `observation_coded`, `observation_string`, `measurement_numeric`, `measurement_coded`, `measurement_simple`, `procedure_simple`, `condition_simple`, `drug_exposure_simple`, `drug_exposure_dose`, and `device_simple`.

A profile is structural. A template gives it semantic meaning.

## Profile groups

A **profile group** is a named family of admissible profiles. For example, `ObservationProfiles` groups `observation_simple`, `observation_coded`, and `observation_string`. Profile groups are used for documentation and routing logic — they describe which shapes are valid within a broad CDM family.

## Registry organisation

**`RegistryGroup`** is an organisational container for templates within a registry file. It has a name, a role, and a list of templates. Registry groups exist for readability and navigation; they carry no semantic meaning.

**`RegistryFragment`** is the top-level structure of a registry YAML file. It contains a list of `RegistryGroup` instances. Multiple fragments can be merged at load time.

## Naming disambiguation

Three things in the codebase are called "group" and they are not the same:

| Name | What it is |
|---|---|
| `OmopGroup` | A semantic set of OMOP concepts defined by ancestry anchors |
| `RegistryGroup` | An organisational grouping of templates in a registry file |
| Profile group | A named family of admissible CDM profiles |

## Anchor ids versus descendant expansion

The runtime resolves `OmopGroup` to its `parent_concepts` anchor ids — not to a database-expanded descendant set. This is intentional: the library is portable and requires no live vocabulary connection.

If your downstream logic needs the full descendant set, use the anchor ids from `entity_concept_ids` as the input to a vocabulary query in your database layer.
