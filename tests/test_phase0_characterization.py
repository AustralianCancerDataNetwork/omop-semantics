"""Phase 0 - characterization tests.

These lock the CURRENT behaviour of omop-semantics (schema + registry + runtime) BEFORE the
planned grounding-config changes (agent-stack: _design/MCP/semantics_gap_analysis.txt, changes
C1-C4 + measurement_simple/device_exposure). They are deliberately behaviour-pinning: several
encode current limitations that a later change is expected to flip. Those are marked
"FLIPS WITH:" so the diff is intentional and reviewed, not silent.

Run: pytest tests/test_phase0_characterization.py
All tests must pass against the pre-change tree.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from omop_semantics import INSTANCE_DIR, SCHEMA_DIR
from omop_semantics.schema import codegen
from omop_semantics.runtime import OmopSemanticEngine
from omop_semantics.runtime.resolver import OmopSemanticResolver
from omop_semantics.runtime.instance_loader import (
    load_profiles,
    load_symbol_module,
    interpolate_profiles,
    merge_instance_files,
)
from omop_semantics.schema.generated_models.omop_semantic_registry import (
    Concept,
    OmopConcept,
    OmopEnum,
    OmopGroup,
    OmopValueSet,
    OmopTemplate,
    OmopCdmProfile,
    RegistryFragment,
    RegistryGroup,
    CdmTable,
)


# ----------------------------------------------------------------------------------------------------
# Golden values captured from the pre-change tree (2026-06-12).
# ----------------------------------------------------------------------------------------------------

GOLDEN_DEMOGRAPHIC_REGISTRY = {
    "Country of birth": {
        "role": "demographic",
        "cdm_profile": "observation_simple",
        "entity_ids": [4155450],
        "value_ids": None,
    },
    "Language spoken": {
        "role": "demographic",
        "cdm_profile": "observation_coded",
        "entity_ids": [4052785],
        "value_ids": [4182347],
    },
    "Postcode": {
        "role": "demographic",
        "cdm_profile": "observation_string",
        "entity_ids": [4083591],
        "value_ids": None,
    },
}

GOLDEN_PROFILES = {
    "observation_simple": ("observation", "observation_concept_id", None),
    "observation_coded": ("observation", "observation_concept_id", "value_as_concept_id"),
    "observation_string": ("observation", "observation_concept_id", "value_as_string"),
    "measurement_numeric": ("measurement", "measurement_concept_id", "value_as_number"),
    "measurement_coded": ("measurement", "measurement_concept_id", "value_as_concept_id"),
    "measurement_simple": ("measurement", "measurement_concept_id", None),  # added: PR1/T1
    "procedure_simple": ("procedure_occurrence", "procedure_concept_id", None),
    "condition_simple": ("condition_occurrence", "condition_concept_id", None),
    "drug_exposure_simple": ("drug_exposure", "drug_concept_id", None),
    "drug_exposure_dose": ("drug_exposure", "drug_concept_id", "dose_value"),
    "device_simple": ("device_exposure", "device_concept_id", None),  # added: PR1/T4
}

GOLDEN_CDM_TABLES = {
    "observation",
    "measurement",
    "drug_exposure",
    "procedure_occurrence",
    "condition_occurrence",
    "device_exposure",  # added: PR1/T4
}


def _profile_paths():
    return [
        INSTANCE_DIR / "profile_groups.yaml",
        SCHEMA_DIR / "profiles" / "omop_staging.yaml",
        SCHEMA_DIR / "profiles" / "omop_modifiers.yaml",
        SCHEMA_DIR / "profiles" / "omop_episodes.yaml",
    ]


# ----------------------------------------------------------------------------------------------------
# P0-1  Load surface: what loads, what doesn't (current reality)
# ----------------------------------------------------------------------------------------------------

def test_p0_demographic_registry_loads_and_compiles():
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=_profile_paths(),
    )
    engine.registry_runtime.compile_index()
    assert engine.registry_runtime.template_names == set(GOLDEN_DEMOGRAPHIC_REGISTRY)


def test_p0_genomic_registry_currently_fails_strict_validation():
    """DOCUMENTS a pre-existing inconsistency: genomic.yaml references value_concept by name and
    carries parent_concepts under class_uri OmopConcept, so it does NOT validate as a
    RegistryFragment today. FLIPS WITH: a future genomic/schema reconciliation (then update this)."""
    with pytest.raises(ValidationError):
        OmopSemanticEngine.from_yaml_paths(
            registry_paths=[INSTANCE_DIR / "genomic.yaml"],
            profile_paths=[],
        )


def test_p0_symbolic_files_load_without_error():
    # Symbolic modules load via load_symbol_module (raw dicts, NOT validated against the models).
    assert len(load_symbol_module(INSTANCE_DIR / "provider_specialty.yaml")) == 17
    # enumerators/valuesets expose no top-level symbol dicts under the current skip rules.
    assert load_symbol_module(INSTANCE_DIR / "enumerators.yaml") == {}
    assert load_symbol_module(INSTANCE_DIR / "valuesets.yaml") == {}


# ----------------------------------------------------------------------------------------------------
# P0-2  Profile catalogue (profiles.yaml) - additive-change guard for measurement_simple/device_simple
# ----------------------------------------------------------------------------------------------------

def test_p0_profile_catalogue_golden():
    profiles = load_profiles(INSTANCE_DIR / "profiles.yaml")
    actual = {
        name: (p.cdm_table, p.concept_slot, p.value_slot) for name, p in profiles.items()
    }
    assert actual == GOLDEN_PROFILES


# ----------------------------------------------------------------------------------------------------
# P0-3  CdmTable enum. device_exposure added in PR1/T4 (was the "FLIPS WITH C4" lock).
# ----------------------------------------------------------------------------------------------------

def test_p0_cdm_table_enum_members():
    assert {m.value for m in CdmTable} == GOLDEN_CDM_TABLES
    assert "device_exposure" in {m.value for m in CdmTable}


# ----------------------------------------------------------------------------------------------------
# P0-4  Resolver contract (per semantic-object type)
# ----------------------------------------------------------------------------------------------------

def test_p0_resolver_concept():
    r = OmopSemanticResolver()
    assert r.resolve(OmopConcept(class_uri="OmopConcept", name="c", concept_id=99)) == {99}


def test_p0_resolver_enum():
    r = OmopSemanticResolver()
    e = OmopEnum(
        class_uri="OmopEnum",
        name="e",
        enum_members=[Concept(concept_id=1), Concept(concept_id=2)],
    )
    assert r.resolve(e) == {1, 2}


def test_p0_resolver_group_single_and_multi_parent():
    r = OmopSemanticResolver()
    single = OmopGroup(class_uri="OmopGroup", name="g1", parent_concepts=[Concept(concept_id=5)])
    multi = OmopGroup(
        class_uri="OmopGroup",
        name="g2",
        parent_concepts=[Concept(concept_id=10), Concept(concept_id=20), Concept(concept_id=30)],
    )
    assert r.resolve(single) == {5}
    # The multi-parent OmopGroup is the Mode-1 grounding-profile shape; lock it explicitly.
    assert r.resolve(multi) == {10, 20, 30}


def test_resolver_value_set_unions_members():
    """C3: resolve(OmopValueSet) returns the UNION of its members' resolved ids (was TypeError pre-C3)."""
    r = OmopSemanticResolver()
    vs = OmopValueSet(
        class_uri="OmopValueSet",
        name="vs",
        members=[
            OmopConcept(class_uri="OmopConcept", name="c", concept_id=1),
            OmopGroup(class_uri="OmopGroup", name="g",
                      parent_concepts=[Concept(concept_id=2), Concept(concept_id=3)]),
        ],
    )
    assert r.resolve(vs) == {1, 2, 3}
    # empty value set resolves to the empty set (not an error)
    assert r.resolve(OmopValueSet(class_uri="OmopValueSet", name="empty", members=[])) == set()


# ----------------------------------------------------------------------------------------------------
# P0-5  Template entity_concept range
# ----------------------------------------------------------------------------------------------------

def _profile():
    return OmopCdmProfile(
        name="measurement_simple",
        cdm_table="measurement",
        concept_slot="measurement_concept_id",
    )


def test_template_with_value_set_entity_compiles():
    """C2 + C3: an OmopValueSet entity now validates and compiles to the union of member ids.
    This is the staging-style value-set shape (e.g. group_stage_entity), authored inline."""
    vs = OmopValueSet(
        class_uri="OmopValueSet",
        name="Group Stage Values",
        members=[
            OmopGroup(class_uri="OmopGroup", name="StageI", parent_concepts=[Concept(concept_id=1633306)]),
            OmopGroup(class_uri="OmopGroup", name="StageII", parent_concepts=[Concept(concept_id=1634209)]),
        ],
    )
    tpl = OmopTemplate(name="group_stage", role="staging", entity_concept=vs, cdm_profile=_profile())
    engine = OmopSemanticEngine.from_instances(
        RegistryFragment(groups=[RegistryGroup(name="g", role="staging", registry_members=[tpl])])
    )
    engine.registry_runtime.compile_index()
    assert engine.registry_runtime.get("group_stage")["entity_concept_ids"] == {1633306, 1634209}


def test_p0_template_with_multi_anchor_group_compiles_to_all_ids():
    """Positive lock for the Mode-1 default shape: a template whose entity is one OmopGroup with
    many parent_concepts compiles to the full anchor id set."""
    tpl = OmopTemplate(
        name="measurement_grounding_default",
        role="measurement",
        entity_concept=OmopGroup(
            class_uri="OmopGroup",
            name="anchors",
            parent_concepts=[Concept(concept_id=i) for i in (10, 20, 30)],
        ),
        cdm_profile=_profile(),
    )
    fragment = RegistryFragment(
        groups=[RegistryGroup(name="g", role="grounding", registry_members=[tpl])]
    )
    engine = OmopSemanticEngine.from_instances(fragment)
    engine.registry_runtime.compile_index()
    compiled = engine.registry_runtime.get("measurement_grounding_default")
    assert compiled["entity_concept_ids"] == {10, 20, 30}
    assert compiled["cdm_profile"].name == "measurement_simple"
    assert compiled["value_concept_ids"] is None


# ----------------------------------------------------------------------------------------------------
# P0-6  Whole-registry compiled golden (lock the existing registry's resolved output)
# ----------------------------------------------------------------------------------------------------

def test_p0_demographic_compiled_registry_matches_golden():
    engine = OmopSemanticEngine.from_yaml_paths(
        registry_paths=[INSTANCE_DIR / "demographic.yaml"],
        profile_paths=[INSTANCE_DIR / "profile_groups.yaml"],
    )
    engine.registry_runtime.compile_index()

    snapshot = {}
    for name in engine.registry_runtime.template_names:
        c = engine.registry_runtime.get(name)
        snapshot[name] = {
            "role": c["role"],
            "cdm_profile": c["cdm_profile"].name,
            "entity_ids": sorted(c["entity_concept_ids"]),
            "value_ids": sorted(c["value_concept_ids"]) if c["value_concept_ids"] else None,
        }
    assert snapshot == GOLDEN_DEMOGRAPHIC_REGISTRY


# ----------------------------------------------------------------------------------------------------
# P0-7  instance_loader behaviours the grounding-profile loading relies on
# ----------------------------------------------------------------------------------------------------

def test_p0_interpolate_profiles_expands_named_cdm_profile():
    profiles = load_profiles(INSTANCE_DIR / "profiles.yaml")
    group = {
        "name": "g",
        "registry_members": [
            {"name": "tpl", "role": "demographic", "cdm_profile": "observation_simple"}
        ],
    }
    interpolate_profiles(group, profiles)
    member = group["registry_members"][0]
    assert member["cdm_profile"] == {
        "name": "observation_simple",
        "cdm_table": "observation",
        "concept_slot": "observation_concept_id",
        "value_slot": None,
    }
    assert "concept_slot" not in member and "value_slot" not in member


def test_p0_interpolate_profiles_unknown_profile_raises():
    profiles = load_profiles(INSTANCE_DIR / "profiles.yaml")
    group = {
        "name": "g",
        "registry_members": [{"name": "tpl", "cdm_profile": "does_not_exist"}],
    }
    with pytest.raises(KeyError):
        interpolate_profiles(group, profiles)


def test_p0_merge_instance_files_rejects_duplicate_group(tmp_path):
    profiles = load_profiles(INSTANCE_DIR / "profiles.yaml")
    f = tmp_path / "dup.yaml"
    f.write_text(
        "groups:\n"
        "  - name: dupe\n"
        "    registry_members: []\n"
        "  - name: dupe\n"
        "    registry_members: []\n"
    )
    with pytest.raises(ValueError):
        merge_instance_files([f], profiles)


# ----------------------------------------------------------------------------------------------------
# P0-8  Generated-model drift guard
#
# The committed pydantic models are produced in code by `omop_semantics.schema.codegen`
# (CLI: `omop-semantics gen-models`), which calls the LinkML PydanticGenerator with the generation
# options pinned there (currently `empty_list_for_multivalued_slots = False` = the linkml 1.11.x
# default). This guard regenerates via the SAME code path and compares exactly - so the test and the
# CLI can never disagree on flags. Only the two runtime-imported modules are generated; `template_set`
# is vestigial. If this fails after a schema change, run `omop-semantics gen-models` and commit.
# ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("module", list(codegen.GEN_TARGETS))
def test_p0_generated_models_match_codegen(module):
    committed = (codegen.GENERATED_DIR / f"{module}.py").read_text()
    fresh = codegen.render_module(codegen.GEN_TARGETS[module])
    assert committed == fresh, (
        f"{module}.py is out of sync with its schema. "
        f"Regenerate with: omop-semantics gen-models"
    )


# ----------------------------------------------------------------------------------------------------
# PR1  Device enablement (T4) — device_exposure CdmTable + device_simple profile are usable end-to-end.
# ----------------------------------------------------------------------------------------------------

def test_pr1_device_template_compiles():
    tpl = OmopTemplate(
        name="device_grounding_default",
        role="device",
        entity_concept=OmopGroup(
            class_uri="OmopGroup",
            name="device anchors",
            parent_concepts=[Concept(concept_id=4126705)],  # SNOMED Physical object
        ),
        cdm_profile=OmopCdmProfile(
            name="device_simple",
            cdm_table="device_exposure",
            concept_slot="device_concept_id",
        ),
    )
    engine = OmopSemanticEngine.from_instances(
        RegistryFragment(groups=[RegistryGroup(name="g", role="grounding", registry_members=[tpl])])
    )
    engine.registry_runtime.compile_index()
    compiled = engine.registry_runtime.get("device_grounding_default")
    assert compiled["cdm_profile"].cdm_table == "device_exposure"
    assert compiled["entity_concept_ids"] == {4126705}
