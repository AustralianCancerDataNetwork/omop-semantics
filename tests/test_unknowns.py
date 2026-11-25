from pathlib import Path

import pytest
from pydantic import ValidationError

from omop_semantics import UNKNOWN
from omop_semantics.runtime.default_valuesets import runtime
from omop_semantics.unknowns import UnknownReason, UnknownValue, _load_unknowns


def test_unknown_catalogue_contains_exact_ids_and_reasons() -> None:
    assert {
        key: (value.concept_id, value.reason)
        for key, value in UNKNOWN.items()
    } == {
        "generic": (4129922, "missing"),
        "cob": (40482029, "missing"),
        "therapeutic_regimen": (4207655, "mapping_failed"),
    }


def test_removed_unknown_keys_are_absent() -> None:
    removed = {
        "drug_trial",
        "cancer",
        "grade",
        "stage",
        "stage_edition",
        "gender",
        "condition",
        "unknown_drug_or_placebo",
    }
    assert removed.isdisjoint(UNKNOWN)


def test_unknown_catalogue_is_read_only_and_labels_are_keys() -> None:
    with pytest.raises(TypeError):
        UNKNOWN["other"] = UnknownValue(1, "other", UnknownReason.missing)

    assert all(value.label == key for key, value in UNKNOWN.items())


def test_runtime_does_not_expose_unknowns_value_set() -> None:
    assert not hasattr(runtime, "unknowns")


def test_unknown_catalogue_rejects_an_unknown_reason(tmp_path: Path) -> None:
    path = tmp_path / "unknowns.yaml"
    path.write_text(
        "unknowns:\n"
        "  - label: generic\n"
        "    concept_id: 4129922\n"
        "    reason: not_a_reason\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        _load_unknowns(path)


def test_unknown_catalogue_rejects_duplicate_labels(tmp_path: Path) -> None:
    path = tmp_path / "unknowns.yaml"
    path.write_text(
        "unknowns:\n"
        "  - label: generic\n"
        "    concept_id: 4129922\n"
        "    reason: missing\n"
        "  - label: generic\n"
        "    concept_id: 40482029\n"
        "    reason: missing\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate unknown label"):
        _load_unknowns(path)
