"""Serializable authoring and binding contracts for semantic projection."""

from enum import StrEnum
from typing import Annotated, Generic, Literal, Self, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
    model_validator,
)

from omop_semantics.schema.generated_models.omop_semantic_registry import CdmTable
from omop_semantics.unknowns import UnknownReason

Name = Annotated[
    str, StringConstraints(min_length=1, pattern=r"^[a-zA-Z_][a-zA-Z_0-9.-]*$")
]
SourceRef = Annotated[str, StringConstraints(min_length=1)]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RoleInput(_Model):
    role: Name


class ContextInput(_Model):
    context: Name


Input = RoleInput | ContextInput


class MembershipPredicate(_Model):
    source: Input
    test: Literal["in", "not_in"]
    codes: tuple[StrictStr, ...] = ()
    codes_from: tuple[Name, ...] = ()

    @model_validator(mode="after")
    def require_codes(self) -> Self:
        if bool(self.codes) == bool(self.codes_from):
            raise ValueError("give exactly one of codes or codes_from")
        return self


class AnsweredPredicate(_Model):
    source: Input
    test: Literal["answered", "unanswered"]


Predicate = Annotated[
    MembershipPredicate | AnsweredPredicate, Field(discriminator="test")
]


class ConstraintKind(StrEnum):
    exact = "exact"
    members = "members"
    descendants = "descendants"
    composite = "composite"
    standard_only = "standard_only"
    domain = "domain"


class ClinicalDomain(StrEnum):
    """Domains supported for event concepts in the CDM projection contract."""

    condition = "Condition"
    device = "Device"
    drug = "Drug"
    episode = "Episode"
    measurement = "Measurement"
    observation = "Observation"
    procedure = "Procedure"
    specimen = "Specimen"
    visit = "Visit"


class DomainConstraint(_Model):
    kind: Literal["domain"]
    reference: ClinicalDomain


class RegistryConstraint(_Model):
    kind: Literal["exact", "members", "descendants", "composite"]
    reference: Name


class StandardConstraint(_Model):
    kind: Literal["standard_only"]
    reference: None = None


Constraint = Annotated[
    DomainConstraint | RegistryConstraint | StandardConstraint,
    Field(discriminator="kind"),
]


class ConceptMapEntry(_Model):
    code: StrictStr
    concept: Name


class NumberMapEntry(_Model):
    code: StrictStr
    number: Number


MapEntry = TypeVar("MapEntry", bound=ConceptMapEntry | NumberMapEntry)


class InlineMap(_Model, Generic[MapEntry]):
    code_map: Annotated[tuple[MapEntry, ...], Field(min_length=1)]


class RegistryLabelMap(_Model):
    registry_labels: Name


class ExternalMap(_Model):
    external_map: Name


class BindingMapEntry(_Model):
    codes_from: Name
    concept: Name


class BindingMap(_Model):
    binding_codes: Annotated[tuple[BindingMapEntry, ...], Field(min_length=1)]


CodedMap = InlineMap[ConceptMapEntry] | RegistryLabelMap | ExternalMap | BindingMap
NumericMap = InlineMap[NumberMapEntry] | ExternalMap
CodeMap = CodedMap | NumericMap


class Derivation(_Model):
    target_slot: Name
    source: Input
    mapping: CodeMap
    when: Predicate | None = None
    required: bool = False


class DateSource(_Model):
    source: Input
    when: Predicate | None = None


class RowContext(_Model):
    event_date: tuple[DateSource, ...] = ()
    visit: Input | None = None
    care_site: Input | None = None


class SpecialMode(StrEnum):
    drop = "drop"
    fail = "fail"
    keep_as_value = "keep_as_value"


class SpecialValue(_Model):
    source: Input
    mode: SpecialMode
    when: Predicate
    reason: UnknownReason
    unknown: Name | None = None


class UnitConversion(_Model):
    unit: Name
    factor: Annotated[Number, Field(gt=0)]
    offset: Number = 0


class UnitPolicy(_Model):
    source: Input
    allowed: Name | None = None
    canonical: Name | None = None
    conversions: tuple[UnitConversion, ...] = ()

    @model_validator(mode="after")
    def require_canonical_unit(self) -> Self:
        if self.conversions and self.canonical is None:
            raise ValueError("conversions require a canonical unit")
        return self


class Presence(_Model):
    kind: Literal["presence"]


class Coded(_Model):
    kind: Literal["coded"]
    source: Input
    mapping: CodedMap | None = None


class Ordinal(_Model):
    kind: Literal["ordinal"]
    source: Input
    mapping: CodedMap | None = None
    order: Annotated[tuple[Name, ...], Field(min_length=1)]


class Numeric(_Model):
    kind: Literal["numeric"]
    source: Input
    operator: Input | None = None


class NumericFromCode(_Model):
    kind: Literal["numeric_from_code"]
    source: Input
    mapping: NumericMap


class NumericWithUnit(_Model):
    kind: Literal["numeric_with_unit"]
    source: Input
    unit: UnitPolicy
    operator: Input | None = None
    range_low: Input | None = None
    range_high: Input | None = None


class PartialDate(_Model):
    kind: Literal["partial_date"]
    year: Input
    month: Input | None = None
    day: Input | None = None

    @model_validator(mode="after")
    def day_requires_month(self) -> Self:
        if self.day is not None and self.month is None:
            raise ValueError("day requires month input")
        return self


Value = Annotated[
    Presence
    | Coded
    | Ordinal
    | Numeric
    | NumericFromCode
    | NumericWithUnit
    | PartialDate,
    Field(discriminator="kind"),
]


class Row(_Model):
    id: Name
    profile: Name
    concept: Input | Name
    constraints: tuple[Constraint, ...] = ()
    value: Value
    context: RowContext = Field(default_factory=RowContext)
    derivations: tuple[Derivation, ...] = ()
    suppress_when: Predicate | None = None
    special_values: tuple[SpecialValue, ...] = ()
    required: bool = True


class Link(_Model):
    source_row: Name
    mechanism: Name
    target_row: Name | None = None
    target_item: Input | None = None
    target_table: CdmTable | None = None
    when: Predicate | None = None

    required_target: bool = True

    @model_validator(mode="after")
    def validate_endpoint(self) -> Self:
        if self.target_row is not None:
            if self.target_item is not None or self.target_table is not None:
                raise ValueError("choose a local row or a bound target")
        elif self.target_item is None or self.target_table is None:
            raise ValueError("supply target_row or both target_item and target_table")
        return self


class OmopShape(_Model):
    name: Name
    version: SourceRef
    roles: tuple[Name, ...] = ()
    context: tuple[Name, ...] = ()
    optional_roles: tuple[Name, ...] = ()
    optional_context: tuple[Name, ...] = ()
    code_groups: tuple[Name, ...] = ()
    rows: Annotated[tuple[Row, ...], Field(min_length=1)]
    links: tuple[Link, ...] = ()
    notes: tuple[str, ...] = ()


class ShapeBinding(_Model):
    """Map role and context names to opaque keys in a source record."""

    shape: Name
    roles: dict[Name, SourceRef] = Field(default_factory=dict)
    context: dict[Name, SourceRef] = Field(default_factory=dict)
    codes: dict[Name, Annotated[tuple[StrictStr, ...], Field(min_length=1)]] = Field(
        default_factory=dict
    )
