# Schema & Instances

## File layout

The package ships two asset directories:

```
src/omop_semantics/schema/
├── configuration/          # LinkML schema definitions
│   ├── core/               # Base primitives, profiles, templates, named-set schema
│   ├── registry/           # Registry and fragment structures
│   └── profiles/           # Domain profile modules (staging, modifiers, episodes)
└── instances/              # YAML instance files (the authoring surface)
    ├── enumerators.yaml
    ├── valuesets.yaml
    ├── profiles.yaml
    ├── profile_groups.yaml
    ├── demographic.yaml
    ├── genomic.yaml
    └── provider_specialty.yaml
```

The `instances/` directory is where the semantic conventions live. The `configuration/` directory contains the LinkML schemas that validate them.

## Instance files

### `enumerators.yaml`

Defines the named enums and groups used by the value-set runtime. Each entry is an `OmopEnum` or `OmopGroup` with a name and its members. These are loaded into `CDMSemanticUnits` and indexed by name for use by the value-set compiler.

Example:
```yaml
named_enumerators:
  - name: genomic_value_group
    class_uri: OmopEnum
    enum_members:
      - concept_id: 9191
        label: genomic_positive
      - concept_id: 9189
        label: genomic_negative
```

### `valuesets.yaml`

Groups named semantic objects into top-level runtime namespaces. A
`semantic_units` entry can be a simple string reference or a named composite
mapping. Composite units combine at most one descendant-expanding group with
exact enums or named concepts.

```yaml
valuesets:
  - name: genomic
    semantic_units:
      - genomic_value_group
      - genomic_mapped_types
  - name: staging
    semantic_units:
      - t_stage_concepts
      - n_stage_concepts
      - group_stage_concepts
  - name: cancer_procedures
    semantic_units:
      - name: cancer_indicating_surgery
        notes: Cancer-directed surgery with exact members.
        named_groups:
          - cancer_indicating_surgery_parent_concepts
        named_enumerators:
          - cancer_indicating_surgery_point_concepts
```

Value-set names become top-level attributes such as `runtime.genomic`. Semantic
unit names become the next level, such as
`runtime.cancer_procedures.cancer_indicating_surgery`. Typed references inside a
composite are constituents, not additional semantic-unit paths in that value set.

### `profiles.yaml`

Defines the CDM row shapes available to templates. Each profile names the target table, the concept slot, and (optionally) the value slot.

```yaml
profiles:
  - name: observation_coded
    cdm_table: observation
    concept_slot: observation_concept_id
    value_slot: value_as_concept_id
  - name: measurement_numeric
    cdm_table: measurement
    concept_slot: measurement_concept_id
    value_slot: value_as_number
```

This file is the authoritative catalogue of built-in CDM profiles. Registry instance files refer to profiles by name and the engine resolves them from here at load time.

### `profile_groups.yaml`

Defines named families of profiles for documentation and routing:

```yaml
ObservationProfiles:
  class_uri: RegistryGroup
  role: observation
  members:
    - observation_simple
    - observation_coded
    - observation_string
```

These are available via `engine.profile_runtime.list_groups()` when the file is passed to `profile_paths`.

### Registry instance files (`demographic.yaml`, etc.)

These define the actual semantic templates. Each file contains a `groups:` list of `RegistryGroup` entries, each with `registry_members:` — the templates.

Templates in these files refer to CDM profiles by name:

```yaml
- name: Country of birth
  role: demographic
  entity_concept:
    class_uri: OmopGroup
    name: Country of Birth
    parent_concepts:
      - concept_id: 4155450
        label: Country of birth
  cdm_profile: observation_simple
```

The string `observation_simple` is resolved against `profiles.yaml` when loading through `OmopSemanticEngine.from_yaml_paths()`.

## Profile resolution at load time

When `OmopSemanticEngine.from_yaml_paths()` loads a registry file, it checks whether any template member uses a string-named `cdm_profile`. If so, it expands those names against the CDM profile catalogue before validating the file as a `RegistryFragment`. Files that already contain fully-expanded profile objects are loaded directly.

The catalogue used defaults to the shipped `profiles.yaml`. To substitute a custom catalogue, pass `profiles_path` to `from_yaml_paths()`.

## Adding your own definitions

To extend the shipped definitions with project-specific conventions, author your own instance files following the same structure and pass them to `from_yaml_paths()`:

```python
engine = OmopSemanticEngine.from_yaml_paths(
    registry_paths=[
        INSTANCE_DIR / "demographic.yaml",   # shipped
        Path("my_project/oncology.yaml"),     # project-specific
    ],
    profile_paths=[
        INSTANCE_DIR / "profile_groups.yaml",
    ],
)
```

Multiple registry files are merged into a single runtime registry. Template names must be unique across all files.

## Regenerating the Pydantic models

The Pydantic models in `schema/generated_models/` are generated from the LinkML schemas. If you change a schema, regenerate with:

```bash
omop-semantics gen-models
```

To check whether the committed models are in sync without writing:

```bash
omop-semantics gen-models --check
```

Run these commands with the project's own virtual environment (not a workspace-level environment) to ensure the correct `linkml` version is used.
