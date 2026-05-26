from __future__ import annotations

from pathlib import Path

from omop_semantics import load


def test_load_compatibility_api_builds_concept_registry(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    instance_path = tmp_path / "instances.yaml"

    schema_path.write_text(
        """
enums:
  ConceptRole:
    permissible_values:
      demographic:
        description: Demographic concepts
      unknown:
        description: Unknown concepts
classes:
  OmopConcept: {}
  ConceptGroup: {}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    instance_path.write_text(
        """
CountryOfBirth:
  class_uri: OmopConcept
  concept_id: 4155450
  label: Country of birth
  role: demographic

UnknownDemographic:
  class_uri: OmopConcept
  concept_id: 0
  label: default unknown
  role: unknown

DemographyConcepts:
  class_uri: ConceptGroup
  name: DemographyConcepts
  role: demographic
  members:
    - CountryOfBirth
""".strip()
        + "\n",
        encoding="utf-8",
    )

    registry = load(
        schema_paths=[schema_path],
        instance_paths=[instance_path],
    )

    assert registry.by_label("Country of birth") == 4155450
    assert registry.is_role(4155450, "demographic")
    assert registry.group_members("DemographyConcepts") == (4155450,)
    assert registry.default_unknown() == 0
