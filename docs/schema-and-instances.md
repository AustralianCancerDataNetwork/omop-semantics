# Schema And Instances

This page explains how the shipped authoring assets are organized.

## Canonical authoring assets

The package currently ships a compact set of canonical instance files under:

`src/omop_semantics/schema/instances/`

Current top-level instances include:

- `enumerators.yaml`
- `valuesets.yaml`
- `profiles.yaml`
- `profile_groups.yaml`
- `demographic.yaml`
- `genomic.yaml`
- `provider_specialty.yaml`

These are the files to treat as the main built-in authoring assets when you are
working with the current package.

## Schema organization

The schema configuration is split into:

- `configuration/core/`
  Base semantic primitives, profiles, templates, and named-set definitions.

- `configuration/registry/`
  Registry- and template-oriented structures.

- `configuration/profiles/`
  Domain-specific symbolic profile modules such as staging, modifiers, and
  episodes.

## What each instance file family is for

### `enumerators.yaml`

Named enums and groups used to build the stable value-set runtime.

### `valuesets.yaml`

High-level namespaces that bundle semantic units together for runtime access
such as `runtime.types` or `runtime.staging`.

### `profiles.yaml`

Generic OMOP row shapes:

- table
- concept slot
- optional value slot

These are structural, not fully semantic, on their own.

### `profile_groups.yaml`

Families of valid profiles. These describe admissible shape sets such as the
observation or measurement profile families.

### domain-specific instance files

Files like `demographic.yaml` and `genomic.yaml` carry concrete semantic
templates and semantic objects.

## Canonical versus compatibility surfaces

It is helpful to distinguish:

- **authoring assets**
  YAML + LinkML schema files in `schema/`

- **runtime surfaces**
  Python APIs that consume those assets

The main runtime surfaces are documented in [Usage](usage.md).

## About draft and transitional content

Earlier planning notes referred to draft or transitional content such as
`todo/` or older experimental schema directories. The important Phase 0
principle is:

- canonical shipped assets should stay easy to identify
- draft or archival content should not sit ambiguously beside them

In this checkout, the main shipped instance set is already fairly compact. If
new provisional content is added later, it should be clearly marked as draft or
archival rather than mixed into the canonical instance set silently.
