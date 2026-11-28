import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest
from ruamel.yaml import YAML

from omop_semantics.links import field_concept_id
from omop_semantics.projection import (
    BindingError,
    BindingIssue,
    BindingIssueCode,
    BoundRow,
    OmopShape,
    ShapeBinding,
    ShapeLoadError,
    ShapeRuntime,
)
from omop_semantics.runtime.default_valuesets import runtime as registry

FIXTURES = Path(__file__).parent / "fixtures" / "shape_projection"
YAML_LOADER = YAML(typ="safe")
GOLDEN = YAML_LOADER.load(FIXTURES / "expected_bundles.yaml")

MEASUREMENT = registry.measurements_numeric.lab_measurements.fev1
OBSERVATION = (
    registry.observations.family_history_observation.family_history_of_clinical_finding
)
PRIMARY = registry.condition_modifiers.condition_status.primary_diagnosis
ANCHOR = next(iter(registry.condition_modifiers.metastatic_disease_concepts.parent_ids))


class Oracle:
    def is_descendant(self, concept_id, ancestor_id):
        return concept_id == MEASUREMENT and ancestor_id == ANCHOR

    def is_standard(self, concept_id):
        return concept_id == ANCHOR

    def domain_of(self, concept_id):
        return "Condition" if concept_id == ANCHOR else "Measurement"


@pytest.fixture
def runtime():
    return ShapeRuntime.from_yaml_paths(
        [FIXTURES / "site.yaml"],
        external_maps={"diagnosis-status": {"principal": PRIMARY}},
        registry_version="test-registry",
    )


@pytest.mark.parametrize("case", GOLDEN, ids=[case["name"] for case in GOLDEN])
def test_golden_projection(runtime, case):
    binding = ShapeBinding.model_validate(case["binding"])
    bundle = runtime.project(binding, case["record"])
    transport = json.loads(json.dumps(bundle.to_dict()))
    assert transport["status"] == case["status"]
    assert [row["fields"] for row in transport["rows"]] == case["rows"]
    assert [check["status"] for check in transport["constraint_checks"]] == case.get(
        "checks", []
    )
    assert transport["value_decisions"] == case.get("decisions", [])
    assert transport["links"] == case.get("links", [])
    assert transport["issues"] == case.get("issues", [])
    assert transport["link_decisions"] == case.get("link_decisions", [])
    assert [
        row["value_rank"] for row in transport["rows"] if "value_rank" in row
    ] == case.get("ranks", [])
    assert transport["registry_version"] == "test-registry"
    assert transport["shape_version"] == case["shape_version"]


def test_context_and_links(runtime):
    shape = runtime.get("related_rows")
    binding = ShapeBinding(
        shape=shape.name,
        roles={name: name for name in shape.roles},
        context={name: name for name in shape.context},
    )
    record = {
        "condition": ANCHOR,
        "measurement": MEASUREMENT,
        "observation": OBSERVATION,
        "related": BoundRow("condition_occurrence", 99),
        "modifier": registry.observations.yes_no_answers.yes,
        "form_date": "2024-10-07",
        "visit_date": "2024-10-02",
        "use_form_date": True,
        "visit": 22,
        "status": "principal",
        "link_external": True,
    }
    result = runtime.project(binding, record).to_dict()
    assert result["shape_source"] == str(FIXTURES / "site.yaml")
    assert result["maps"] == {
        "diagnosis-status": sha256(
            json.dumps({"principal": PRIMARY}, separators=(",", ":")).encode()
        ).hexdigest()
    }
    fields = result["rows"][0]["fields"]
    assert fields == {
        "condition_concept_id": ANCHOR,
        "condition_start_date": "2024-10-07",
        "condition_status_concept_id": PRIMARY,
        "visit_occurrence_id": 22,
    }
    assert result["links"] == [
        {
            "source": "measurement",
            "target": {"row": "condition"},
            "mechanism": "measurement",
            "table": "measurement",
            "fields": {
                "measurement_event_id": {"row": "condition"},
                "meas_event_field_concept_id": field_concept_id("condition_occurrence"),
            },
        },
        {
            "source": "observation",
            "target": {"table": "condition_occurrence", "id": 99},
            "mechanism": "observation",
            "table": "observation",
            "fields": {
                "observation_event_id": 99,
                "obs_event_field_concept_id": field_concept_id("condition_occurrence"),
            },
        },
    ]
    fallback = runtime.project(
        binding, record | {"form_date": None, "status": None, "link_external": False}
    )
    assert fallback.status == "ok"
    assert fallback.rows[0].fields["condition_start_date"].isoformat() == "2024-10-02"
    assert "condition_status_concept_id" not in fallback.rows[0].fields
    assert len(fallback.links) == 1
    assert fallback.maps == {}
    no_date = runtime.project(binding, record | {"form_date": np.nan, "visit_date": ""})
    assert no_date.status == "partial"
    assert any(issue.slot == "condition_start_date" for issue in no_date.issues)

    missing = runtime.project(binding, record | {"related": None})
    assert missing.status == "partial"
    assert missing.issues[0].code == "missing_link_target"

    wrong_table = runtime.project(
        binding, record | {"related": {"table": "observation", "id": 99}}
    )
    assert wrong_table.status == "invalid"

    bad_date = runtime.project(binding, record | {"form_date": "2024-02-30"})
    assert bad_date.status == "invalid"


def test_registry_and_oracle_constraints(runtime):
    binding = ShapeBinding(shape="anchor_filter", roles={"concept": "c"})
    assert (
        runtime.project(binding, {"c": MEASUREMENT}).constraint_checks[0].status
        == "deferred"
    )
    with_oracle = ShapeRuntime.from_yaml_paths(
        [FIXTURES / "site.yaml"],
        oracle=Oracle(),
        external_maps={"diagnosis-status": {"principal": PRIMARY}},
    )
    assert (
        with_oracle.project(binding, {"c": MEASUREMENT}).constraint_checks[0].status
        == "passed"
    )
    failed = with_oracle.project(binding, {"c": OBSERVATION})
    assert failed.status == "invalid"
    assert failed.constraint_checks[0].status == "failed"
    assert not failed.rows

    gate = ShapeBinding(
        shape="criteria_gate_condition",
        roles={"concept": "c", "answer": "a"},
        codes={"yes": ("1",), "no": ("0",)},
    )
    assert with_oracle.project(gate, {"c": ANCHOR, "a": 1}).status == "ok"
    assert with_oracle.project(gate, {"c": MEASUREMENT, "a": 1}).status == "invalid"
    assert with_oracle.project(gate, {"c": ANCHOR, "a": []}).status == "invalid"


def test_conversion_and_range(runtime):
    shape = runtime.get("measurement_with_converted_unit")
    binding = ShapeBinding(
        shape=shape.name,
        roles={name: name for name in shape.roles},
        context={name: name for name in shape.context},
    )
    units = registry.measurements_numeric.body_size_units
    record = {
        "concept": MEASUREMENT,
        "value": 100,
        "unit": units.lb,
        "operator": 0,
        "range_low": 70,
        "range_high": 110,
    }
    projected = runtime.project(binding, record)
    assert projected.status == "ok"
    fields = projected.rows[0].fields
    assert fields["value_as_number"] == pytest.approx(45.359237)
    assert fields["range_low"] == pytest.approx(31.7514659)
    assert fields["range_high"] == pytest.approx(49.8951607)
    assert fields["unit_concept_id"] == units.kg
    assert runtime.project(binding, record | {"unit": units.cm}).status == "invalid"
    assert runtime.project(binding, record | {"range_low": 130}).status == "invalid"
    assert runtime.project(binding, record | {"range_low": None}).status == "ok"


def test_partial_invalid_and_context_ids(runtime):
    binding = ShapeBinding(
        shape="partial_date_observation",
        roles={k: k for k in ("concept", "year", "month", "day")},
    )
    assert runtime.project(binding, {"concept": OBSERVATION}).status == "partial"
    assert (
        runtime.project(
            binding, {"concept": OBSERVATION, "year": 2025, "month": 2, "day": 29}
        ).status
        == "invalid"
    )
    assert (
        runtime.project(
            binding, {"concept": OBSERVATION, "year": 2025, "day": 7}
        ).status
        == "invalid"
    )

    binding = ShapeBinding(
        shape="visit_with_care_site",
        roles={"concept": "c"},
        context={"care_site": "site/key"},
    )
    assert (
        runtime.project(binding, {"c": 0, "site/key": 17})
        .rows[0]
        .fields["care_site_id"]
        == 17
    )
    assert runtime.project(binding, {"c": 0, "site/key": 0}).status == "invalid"
    assert runtime.project(binding, {"c": 0}).status == "partial"


def _site(tmp_path, shape):
    path = tmp_path / "site.yaml"
    YAML_LOADER.dump({"shapes": [shape]}, path)
    return path


def test_layers_replace_whole_shapes_in_order_and_discover(tmp_path):
    default = ShapeRuntime.from_yaml_paths()
    base = default.get("presence").model_dump(mode="json")
    first = _site(tmp_path, base | {"version": "2"})
    second = tmp_path / "override.yaml"
    YAML_LOADER.dump({"shapes": [base | {"version": "3"}]}, second)
    layered = ShapeRuntime.from_yaml_paths([first, second])
    assert layered.get("presence").version == "3"
    assert layered.names() == default.names()
    assert ShapeBinding.model_validate_json(
        ShapeBinding(
            shape="presence", roles={"concept": "opaque/key"}
        ).model_dump_json()
    ).roles == {"concept": "opaque/key"}


BASE_ROW = {
    "id": "observation",
    "profile": "observation_simple",
    "concept": {"role": "concept"},
    "value": {"kind": "presence"},
}


@pytest.mark.parametrize(
    ("patch", "key"),
    [
        ({"rows": [BASE_ROW, BASE_ROW]}, "rows: duplicate row id"),
        ({"roles": ["concept", "concept"]}, "roles: duplicate"),
        ({"rows": [BASE_ROW | {"profile": "missing"}]}, "rows.observation.profile"),
        (
            {"rows": [BASE_ROW | {"concept": {"role": "missing"}}]},
            "rows.observation.concept",
        ),
        (
            {"rows": [BASE_ROW | {"concept": {"role": "concept", "context": "x"}}]},
            "rows.observation.concept",
        ),
        (
            {"rows": [BASE_ROW | {"concept": "observations.yes_no_answers.missing"}]},
            "unknown exact concept",
        ),
        (
            {"rows": [BASE_ROW | {"context": {"care_site": {"role": "concept"}}}]},
            "rows.observation.context.care_site",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {"value": {"kind": "numeric", "source": {"role": "concept"}}}
                ]
            },
            "profile must have value slot",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {"value": {"kind": "presence", "source": {"role": "concept"}}}
                ]
            },
            "rows.observation.value.source",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {
                        "suppress_when": {
                            "source": {"role": "concept"},
                            "test": "answered",
                            "codes": ["1"],
                        }
                    }
                ]
            },
            "suppress_when.codes",
        ),
        (
            {"rows": [BASE_ROW | {"constraints": [{"kind": "exact"}]}]},
            "constraints[0].reference",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {
                        "constraints": [
                            {
                                "kind": "descendants",
                                "reference": "observations.yes_no_answers",
                            }
                        ]
                    }
                ]
            },
            "no descendant anchors",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {
                        "constraints": [
                            {"kind": "standard_only", "reference": "Condition"}
                        ]
                    }
                ]
            },
            "constraints[0].reference",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {
                        "derivations": [
                            {
                                "source": {"role": "concept"},
                                "target_slot": "missing",
                                "mapping": {
                                    "registry_labels": "observations.yes_no_answers"
                                },
                            }
                        ]
                    }
                ]
            },
            "derivations[0].target_slot",
        ),
        (
            {
                "links": [
                    {
                        "source_row": "missing",
                        "mechanism": "observation",
                        "target_row": "observation",
                    }
                ]
            },
            "links[0].source_row",
        ),
        (
            {
                "links": [
                    {
                        "source_row": "observation",
                        "mechanism": "missing",
                        "target_row": "missing",
                    }
                ]
            },
            "unknown link mechanism",
        ),
        (
            {
                "links": [
                    {
                        "source_row": "observation",
                        "mechanism": "measurement",
                        "target_row": "missing",
                    }
                ]
            },
            "wrong CDM table",
        ),
        (
            {
                "links": [
                    {
                        "source_row": "observation",
                        "mechanism": "observation",
                        "target_row": "missing",
                    }
                ]
            },
            "links[0].target_row",
        ),
        (
            {
                "links": [
                    {
                        "source_row": "observation",
                        "mechanism": "observation",
                        "target_item": {"role": "concept"},
                    }
                ]
            },
            "supply target_row",
        ),
        (
            {
                "links": [
                    {
                        "source_row": "observation",
                        "mechanism": "observation",
                        "target_item": {"role": "concept"},
                        "target_table": "visit_occurrence",
                    }
                ]
            },
            "Unknown link target table",
        ),
        ({"typo": True}, "shapes.bad.typo"),
    ],
)
def test_compile_errors_include_path_and_key(tmp_path, patch, key):
    shape = {"name": "bad", "version": "1", "roles": ["concept"], "rows": [BASE_ROW]}
    path = _site(tmp_path, shape | patch)
    with pytest.raises(ValueError) as error:
        ShapeRuntime.from_yaml_paths([path])
    assert str(path) in str(error.value)
    assert key in str(error.value)


def test_duplicate_shapes_in_layer(tmp_path):
    path = tmp_path / "site.yaml"
    shape = {
        "name": "duplicate",
        "version": "1",
        "roles": ["concept"],
        "rows": [BASE_ROW],
    }
    YAML_LOADER.dump({"shapes": [shape, shape]}, path)
    with pytest.raises(ValueError, match="shapes.duplicate: duplicate shape"):
        ShapeRuntime.from_yaml_paths([path])


def test_schema_matches_authoring_models():
    schema_path = (
        Path(__file__).parents[1] / "docs" / "schemas" / "omop_shape.schema.json"
    )
    assert json.loads(schema_path.read_text()) == OmopShape.model_json_schema()


def _simple_shape(name, row, **kwargs):
    return {"name": name, "version": "1", "rows": [row], **kwargs}


def test_binding_checks_required_optional_and_unknown_wiring(runtime):
    wrong = ShapeBinding(shape="absent")
    assert runtime.check_binding(wrong) == (
        BindingIssue(BindingIssueCode.unknown_shape, "absent"),
    )
    with pytest.raises(BindingError) as error:
        runtime.project(wrong, {})
    assert error.value.issues == runtime.check_binding(wrong)
    wrong = ShapeBinding(
        shape="numeric_measurement_with_operator",
        roles={"value": "result", "typo": "input"},
        context={"unexpected": "context"},
    )
    assert {(issue.code, issue.name) for issue in runtime.check_binding(wrong)} == {
        ("unknown_role", "typo"),
        ("unbound_role", "concept"),
        ("unbound_role", "operator"),
        ("unknown_context", "unexpected"),
        ("unbound_context", "unit"),
    }
    good = ShapeBinding(
        shape="partial_date_observation", roles={"concept": "c", "year": "y"}
    )
    assert not runtime.check_binding(good)
    assert runtime.project(good, {"c": OBSERVATION, "y": 2026}).status == "ok"


def test_binding_supplies_codes_to_default_shapes(runtime):
    gate = ShapeBinding(
        shape="criteria_gate_condition",
        roles={"concept": "c", "answer": "answer"},
        codes={"yes": ("Y", "1"), "no": ("N", "0")},
    )
    assert runtime.project(gate, {"c": ANCHOR, "answer": "Y"}).status == "ok"
    assert runtime.project(gate, {"c": ANCHOR, "answer": 1.0}).status == "ok"
    for raw in ("N", "", np.nan):
        result = runtime.project(gate, {"c": ANCHOR, "answer": raw})
        assert result.status == "suppressed"
        assert not result.issues
    invalid = runtime.project(gate, {"c": ANCHOR, "answer": "neither"})
    assert invalid.status == "invalid"
    assert invalid.issues[0].code == "special_value_failed"
    observation = gate.model_copy(update={"shape": "yes_no_observation"})
    assert (
        runtime.project(observation, {"c": OBSERVATION, "answer": "N"})
        .rows[0]
        .fields["value_as_concept_id"]
        == registry.observations.yes_no_answers.no
    )
    assert runtime.check_binding(
        observation.model_copy(update={"codes": {"yes": ("Y",), "no": ("Y",)}})
    ) == (BindingIssue(BindingIssueCode.ambiguous_code, "Y"),)
    assert runtime.check_binding(
        gate.model_copy(update={"codes": {"no": ("N",), "unknown": ("X",)}})
    ) == (
        BindingIssue(BindingIssueCode.unknown_code_group, "unknown"),
        BindingIssue(BindingIssueCode.unbound_code_group, "yes"),
    )


@pytest.mark.parametrize(
    ("concept", "value", "status"),
    [
        (np.int64(MEASUREMENT), np.float32(1.5), "ok"),
        (str(MEASUREMENT), "1.5", "ok"),
        (float(MEASUREMENT), 1.5, "ok"),
        (MEASUREMENT, np.nan, "partial"),
        (MEASUREMENT, np.float32("nan"), "partial"),
        (np.datetime64("NaT", "ns"), 1.5, "partial"),
        (True, 1.5, "invalid"),
        (float(MEASUREMENT) + 0.5, 1.5, "invalid"),
        ("+123", 1.5, "invalid"),
        ("１２３", 1.5, "invalid"),
        (MEASUREMENT, float("inf"), "invalid"),
    ],
)
def test_record_scalar_normalization(runtime, concept, value, status):
    binding = ShapeBinding(
        shape="numeric_measurement", roles={"concept": "c", "value": "v"}
    )
    result = runtime.project(binding, {"c": concept, "v": value})
    assert result.status == status
    if status == "ok":
        assert result.rows[0].fields == {
            "measurement_concept_id": MEASUREMENT,
            "value_as_number": 1.5,
        }
    else:
        expected = "missing_input" if status == "partial" else "invalid_input"
        assert [issue.code for issue in result.issues] == [expected]


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize(
    ("source", "issue"), [(None, "missing_input"), ("unmapped", "unmapped_code")]
)
def test_derivation_failures_keep_the_primary_row(tmp_path, required, source, issue):
    shape = ShapeRuntime.from_yaml_paths().get("condition_with_status_role")
    override = shape.model_dump(mode="json", exclude_none=True)
    override["rows"][0]["derivations"][0]["required"] = required
    runtime = ShapeRuntime.from_yaml_paths([_site(tmp_path, override)])
    binding = ShapeBinding(shape=shape.name, roles={"concept": "c", "status": "s"})
    result = runtime.project(binding, {"c": ANCHOR, "s": source})
    assert result.status == ("partial" if required else "ok")
    assert result.rows[0].fields == {"condition_concept_id": ANCHOR}
    assert [(item.slot, item.code) for item in result.issues] == [
        ("condition_status_concept_id", issue),
    ]
    if not required:
        result = runtime.project(
            ShapeBinding(shape=shape.name, roles={"concept": "c"}), {"c": ANCHOR}
        )
        assert result.status == "ok"
        assert result.rows[0].fields == {"condition_concept_id": ANCHOR}


@pytest.mark.parametrize("required_target", [True, False])
def test_local_suppression_is_not_a_missing_target(tmp_path, required_target):
    base = _simple_shape("suppression", BASE_ROW, roles=["concept", "value", "gate"])
    base["rows"][0] = BASE_ROW | {
        "suppress_when": {"source": {"role": "gate"}, "test": "unanswered"}
    }
    base["rows"].append(
        {
            "id": "modifier",
            "profile": "measurement_numeric",
            "concept": {"role": "concept"},
            "value": {"kind": "numeric", "source": {"role": "value"}},
        }
    )
    base["links"] = [
        {
            "source_row": "modifier",
            "mechanism": "measurement",
            "target_row": "observation",
            "required_target": required_target,
        }
    ]
    runtime = ShapeRuntime.from_yaml_paths([_site(tmp_path, base)])
    binding = ShapeBinding(
        shape="suppression", roles={name: name for name in base["roles"]}
    )
    result = runtime.project(binding, {"concept": MEASUREMENT, "value": 1})
    assert result.status == ("suppressed" if required_target else "ok")
    assert not result.issues and not result.links
    assert len(result.rows) == (0 if required_target else 1)
    assert result.to_dict()["link_decisions"] == [
        {
            "source": "modifier",
            "target": "observation",
            "suppressed_source": required_target,
        }
    ]
    missing = runtime.project(
        binding, {"concept": np.nan, "gate": "present", "value": 1}
    )
    assert missing.status == "partial"
    assert not missing.link_decisions


def test_missing_local_target_still_reports_partial(tmp_path):
    base = _simple_shape("missing_target", BASE_ROW, roles=["concept", "modifier"])
    base["rows"].append(
        {
            "id": "modifier",
            "profile": "measurement_numeric",
            "concept": {"role": "modifier"},
            "value": {"kind": "presence"},
        }
    )
    base["links"] = [
        {
            "source_row": "modifier",
            "mechanism": "measurement",
            "target_row": "observation",
        }
    ]
    runtime = ShapeRuntime.from_yaml_paths([_site(tmp_path, base)])
    binding = ShapeBinding(
        shape="missing_target", roles={"concept": "c", "modifier": "m"}
    )
    result = runtime.project(binding, {"m": MEASUREMENT})
    assert result.status == "partial"
    assert [row.row_id for row in result.rows] == ["modifier"]
    assert [issue.code for issue in result.issues] == [
        "missing_input",
        "missing_link_target",
    ]


def test_ordinal_rank_is_metadata_and_rejects_outside_order(tmp_path, runtime):
    shape = runtime.get("histological_grade_value")
    change = shape.model_dump(mode="json", exclude_none=True)
    del change["rows"][0]["value"]["mapping"]
    change["rows"][0]["value"]["order"].reverse()
    runtime = ShapeRuntime.from_yaml_paths([_site(tmp_path, change)])
    binding = ShapeBinding(shape=shape.name, roles={"concept": "c", "answer": "a"})
    grade = registry.condition_modifiers.tumor_grade.grade_2
    result = runtime.project(binding, {"c": MEASUREMENT, "a": grade})
    assert result.rows[0].value_rank == 3
    assert result.rows[0].fields["value_as_concept_id"] == grade
    with pytest.raises(TypeError):
        result.rows[0].fields["value_as_concept_id"] = 0
    transport = result.to_dict()
    transport["rows"][0]["fields"].clear()
    assert result.rows[0].fields
    invalid = runtime.project(binding, {"c": MEASUREMENT, "a": PRIMARY})
    assert invalid.status == "invalid" and invalid.issues


def test_numeric_operator_without_unit(tmp_path):
    row = BASE_ROW | {
        "profile": "measurement_numeric_with_operator",
        "value": {
            "kind": "numeric",
            "source": {"role": "value"},
            "operator": {"role": "operator"},
        },
    }
    path = _site(
        tmp_path, _simple_shape("titre", row, roles=["concept", "value", "operator"])
    )
    runtime = ShapeRuntime.from_yaml_paths([path])
    result = runtime.project(
        ShapeBinding(
            shape="titre", roles={"concept": "c", "value": "v", "operator": "o"}
        ),
        {"c": MEASUREMENT, "v": 5, "o": 0},
    )
    assert result.rows[0].fields == {
        "measurement_concept_id": MEASUREMENT,
        "value_as_number": 5,
        "operator_concept_id": 0,
    }


def test_layer_reports_multiple_named_errors(tmp_path):
    invalid_profile = _simple_shape(
        "profile_error", BASE_ROW | {"profile": "unknown"}, roles=["concept"]
    )
    invalid_value = _simple_shape(
        "value_error", BASE_ROW | {"value": {"kind": "numeric"}}, roles=["concept"]
    )
    path = tmp_path / "catalogue.yaml"
    YAML_LOADER.dump({"shapes": [invalid_profile, invalid_value]}, path)
    with pytest.raises(ShapeLoadError) as error:
        ShapeRuntime.from_yaml_paths([path])
    assert (
        f"{path}: shapes.profile_error.rows.observation.profile"
        in error.value.errors[0]
    )
    assert (
        f"{path}: shapes.value_error.rows.observation.value.source"
        in error.value.errors[1]
    )


_TITRE_ROW = BASE_ROW | {
    "profile": "measurement_numeric_with_operator",
    "value": {
        "kind": "numeric_with_unit",
        "source": {"role": "concept"},
        "unit": {"source": {"role": "concept"}},
    },
}
_WEIGHT_UNITS = "measurements_numeric.body_size_units"
_KG = f"{_WEIGHT_UNITS}.kg"
_LB = f"{_WEIGHT_UNITS}.lb"


def _unit_case(**change):
    row = _TITRE_ROW.copy()
    value = row["value"] | {"unit": row["value"]["unit"] | change}
    return {"rows": [row | {"value": value}]}


def _unit_value_case(**change):
    return {"rows": [_TITRE_ROW | {"value": _TITRE_ROW["value"] | change}]}


def _coded_case(kind="coded", **change):
    row = BASE_ROW | {
        "profile": "observation_coded",
        "value": {"kind": kind, "source": {"role": "concept"}, **change},
    }
    return {"rows": [row]}


def _derivation_case(*rules, **row):
    return {
        "rows": [
            BASE_ROW
            | {
                "profile": "measurement_numeric_with_operator",
                "derivations": list(rules),
                **row,
            }
        ]
    }


_NUMERIC_DERIVATION = {
    "target_slot": "range_low",
    "source": {"role": "concept"},
    "mapping": {"code_map": [{"code": "low", "number": 1}]},
}


@pytest.mark.parametrize(
    ("patch", "key"),
    [
        ({"context": ["same", "same"]}, "context: duplicate name"),
        ({"optional_roles": ["missing"]}, "optional_roles: optional names"),
        ({"optional_context": ["missing"]}, "optional_context: optional names"),
        ({"rows": []}, "rows: Tuple should have at least 1"),
        ({"rows": [BASE_ROW | {"concept": {"context": "missing"}}]}, "unknown context"),
        (
            {
                "rows": [
                    BASE_ROW
                    | {
                        "suppress_when": {
                            "source": {"role": "concept"},
                            "test": "in",
                            "codes_from": ["missing"],
                        }
                    }
                ]
            },
            "unknown code group",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {"suppress_when": {"source": {"role": "concept"}, "test": "in"}}
                ]
            },
            "exactly one of codes or codes_from",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {"constraints": [{"kind": "domain", "reference": "Conditon"}]}
                ]
            },
            "constraints[0].reference",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {"constraints": [{"kind": "members", "reference": "malformed"}]}
                ]
            },
            "expected value_set.unit",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {
                        "constraints": [
                            {"kind": "members", "reference": "observations.missing"}
                        ]
                    }
                ]
            },
            "unknown semantic unit",
        ),
        (
            {
                "rows": [
                    BASE_ROW
                    | {
                        "constraints": [
                            {
                                "kind": "members",
                                "reference": "condition_modifiers.metastatic_disease_concepts",
                            }
                        ]
                    }
                ]
            },
            "no exact members",
        ),
        (
            _coded_case(
                mapping={
                    "registry_labels": "condition_modifiers.metastatic_disease_concepts"
                }
            ),
            "no exact members",
        ),
        (_coded_case(mapping={"external_map": "missing"}), "unknown external map"),
        (
            _coded_case(
                mapping={
                    "registry_labels": "observations.yes_no_answers",
                    "external_map": "also_present",
                }
            ),
            "Extra inputs are not permitted",
        ),
        (_coded_case(mapping={"code_map": []}), "value.mapping"),
        (
            _coded_case(
                mapping={
                    "code_map": [
                        {
                            "code": "Y",
                            "number": 0,
                            "concept": "observations.yes_no_answers.yes",
                        }
                    ]
                }
            ),
            "value.mapping",
        ),
        (
            _coded_case(mapping={"code_map": [{"code": "Y", "number": 0}]}),
            "value.mapping",
        ),
        (
            _coded_case(
                mapping={
                    "code_map": [
                        {"code": "Y", "concept": "observations.yes_no_answers.yes"}
                    ]
                    * 2
                }
            ),
            "duplicate code",
        ),
        (
            _coded_case(
                mapping={
                    "binding_codes": [
                        {
                            "codes_from": "yes",
                            "concept": "observations.yes_no_answers.yes",
                        }
                    ]
                }
            ),
            "unknown code group",
        ),
        (_coded_case("ordinal", order=[]), "value.order"),
        (
            _coded_case("ordinal", order=["observations.yes_no_answers.yes"] * 2),
            "duplicate ordinal concepts",
        ),
        (
            _coded_case(
                "ordinal",
                order=["observations.yes_no_answers.yes"],
                mapping={"registry_labels": "observations.yes_no_answers"},
            ),
            "map has unordered concepts",
        ),
        (_coded_case("numeric_from_code"), "value.mapping"),
        (
            {
                "rows": [
                    BASE_ROW
                    | {
                        "value": {
                            "kind": "partial_date",
                            "year": {"role": "concept"},
                            "day": {"role": "concept"},
                        }
                    }
                ]
            },
            "day requires month",
        ),
        (_unit_value_case(unit=None), "value.unit"),
        (
            {
                "rows": [
                    _TITRE_ROW
                    | {
                        "profile": "measurement_numeric_with_unit",
                        "value": _TITRE_ROW["value"]
                        | {"operator": {"role": "concept"}},
                    }
                ]
            },
            "no operator slot",
        ),
        (
            {"rows": [_TITRE_ROW | {"profile": "measurement_numeric"}]},
            "profile has no unit slot",
        ),
        (
            {
                "rows": [
                    _TITRE_ROW
                    | {
                        "profile": "measurement_numeric_with_unit",
                        "value": _TITRE_ROW["value"]
                        | {"range_low": {"role": "concept"}},
                    }
                ]
            },
            "profile has no range slot",
        ),
        (
            _unit_case(allowed="condition_modifiers.metastatic_disease_concepts"),
            "no exact members",
        ),
        (
            _unit_case(allowed="observations.yes_no_answers", canonical=_KG),
            "must be allowed",
        ),
        (
            _unit_case(conversions=[{"unit": _LB, "factor": 1}]),
            "require a canonical unit",
        ),
        (_unit_case(canonical=_KG, conversions=[{"unit": _LB, "factor": 0}]), "factor"),
        (
            _unit_case(canonical=_KG, conversions=[{"unit": _KG, "factor": 1}]),
            "duplicate or canonical unit",
        ),
        (
            _unit_case(
                canonical=_KG,
                allowed=_WEIGHT_UNITS,
                conversions=[{"unit": "observations.yes_no_answers.yes", "factor": 1}],
            ),
            "unit must be allowed",
        ),
        (
            _derivation_case(_NUMERIC_DERIVATION, _NUMERIC_DERIVATION),
            "duplicate derivation target",
        ),
        (
            _derivation_case(
                _NUMERIC_DERIVATION,
                value=_TITRE_ROW["value"] | {"range_low": {"role": "concept"}},
            ),
            "also supplied by value input",
        ),
        (
            _derivation_case(
                _NUMERIC_DERIVATION
                | {"mapping": {"registry_labels": "observations.yes_no_answers"}}
            ),
            "registry labels map to concepts",
        ),
        (
            _derivation_case(
                _NUMERIC_DERIVATION
                | {
                    "mapping": {
                        "binding_codes": [
                            {
                                "codes_from": "yes",
                                "concept": "observations.yes_no_answers.yes",
                            }
                        ]
                    }
                }
            ),
            "binding code groups map to concepts",
        ),
    ],
)
def test_additional_authoring_validation_rules(tmp_path, patch, key):
    shape = _simple_shape("invalid_shape", BASE_ROW, roles=["concept"]) | patch
    path = _site(tmp_path, shape)
    with pytest.raises(ShapeLoadError) as exc:
        ShapeRuntime.from_yaml_paths([path])
    assert f"{path}: shapes.invalid_shape" in str(exc.value)
    assert key in str(exc.value)


@pytest.mark.parametrize(
    ("kind", "reference", "concept"),
    [
        (
            "exact",
            "observations.yes_no_answers.yes",
            registry.observations.yes_no_answers.yes,
        ),
        (
            "members",
            "observations.yes_no_answers",
            registry.observations.yes_no_answers.no,
        ),
        (
            "composite",
            "observations.yes_no_answers",
            registry.observations.yes_no_answers.yes,
        ),
        ("descendants", "condition_modifiers.metastatic_disease_concepts", ANCHOR),
    ],
)
def test_decidable_checks_run_without_oracle(tmp_path, kind, reference, concept):
    row = BASE_ROW | {"constraints": [{"kind": kind, "reference": reference}]}
    shape = _simple_shape("test_constraint", row, roles=["concept"])
    runtime = ShapeRuntime.from_yaml_paths([_site(tmp_path, shape)])
    binding = ShapeBinding(shape=shape["name"], roles={"concept": "concept"})
    assert (
        runtime.project(binding, {"concept": concept}).constraint_checks[0].status
        == "passed"
    )
    if kind != "descendants":
        rejected = runtime.project(binding, {"concept": ANCHOR})
        assert rejected.status == "invalid"
        assert rejected.constraint_checks[0].status == "failed"


def test_descendant_exclusions_are_scoped_to_their_group(tmp_path):
    from omop_semantics.runtime.value_sets import (
        RuntimeSemanticUnit,
        RuntimeValueSet,
        RuntimeValueSets,
    )
    from omop_semantics.schema.generated_models.omop_named_sets import CDMSemanticUnits

    unit = RuntimeSemanticUnit(
        CDMSemanticUnits.model_validate(
            {
                "name": "mixed",
                "named_groups": [
                    {
                        "class_uri": "OmopGroup",
                        "name": "first",
                        "parent_concepts": [
                            {"label": "first_anchor", "concept_id": MEASUREMENT}
                        ],
                        "excluded_parent_concepts": [
                            {"label": "exclusion", "concept_id": ANCHOR}
                        ],
                    },
                    {
                        "class_uri": "OmopGroup",
                        "name": "second",
                        "parent_concepts": [
                            {"label": "second_anchor", "concept_id": ANCHOR}
                        ],
                    },
                ],
            }
        )
    )
    local_registry = RuntimeValueSets(
        {"test": RuntimeValueSet("test", {"mixed": unit})}
    )
    row = BASE_ROW | {
        "constraints": [{"kind": "descendants", "reference": "test.mixed"}]
    }
    shape = _simple_shape("group_scope", row, roles=["concept"])
    runtime = ShapeRuntime.from_yaml_paths(
        default_path=_site(tmp_path, shape), registry=local_registry
    )
    binding = ShapeBinding(shape=shape["name"], roles={"concept": "concept"})
    assert (
        runtime.project(binding, {"concept": ANCHOR}).constraint_checks[0].status
        == "passed"
    )
