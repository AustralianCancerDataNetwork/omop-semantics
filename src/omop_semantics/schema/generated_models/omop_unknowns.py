from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.11.0"
version = "None"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'omop',
     'default_range': 'string',
     'description': 'Behavioural fallbacks, deliberately kept out of the value-set '
                    'runtime.\n',
     'id': 'https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/omop_unknowns',
     'imports': ['linkml:types', 'omop_base'],
     'name': 'omop_unknowns',
     'prefixes': {'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'omop': {'prefix_prefix': 'omop',
                           'prefix_reference': 'https://athena.ohdsi.org/search-terms/terms/'}},
     'source_file': 'src/omop_semantics/schema/configuration/core/omop_unknowns.yaml',
     'title': 'OMOP Behavioural Fallback Concepts'} )

class UnknownReason(str, Enum):
    missing = "missing"
    """
    The source value was absent.
    """
    mapping_failed = "mapping_failed"
    """
    A source value was present but could not be mapped.
    """



class OmopSemanticObject(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True,
         'from_schema': 'https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/omop_base'})

    class_uri: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })


class OmopGroup(OmopSemanticObject):
    """
    Named group of OMOP concepts defined by their membership in a particular group, such  as hierarchy and / or domain. Importantly, this is not a static definition and if the vocabularies are updated, the membership of these groups may change. This is intended to be used for defining sets of concepts that are used in semantic definitions, such as the set of all  T stage concepts.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/omop_base',
         'slot_usage': {'class_uri': {'equals_string': 'OmopGroup',
                                      'name': 'class_uri'}}})

    parent_concepts: Optional[list[Concept]] = Field(default=None, description="""Semantic parent concepts or grouping parents.""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopGroup']} })
    excluded_parent_concepts: Optional[list[Concept]] = Field(default=None, description="""Parent concepts whose descendant closure is excluded from the positive group membership. Use this when a governed value set is defined as one hierarchy closure minus another, such as SACT drugs excluding supportive medications.
""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopGroup']} })
    class_uri: Literal["OmopGroup"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopGroup'} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })


class OmopConcept(OmopSemanticObject):
    """
    A single OMOP concept with semantic annotations
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/omop_base',
         'slot_usage': {'class_uri': {'equals_string': 'OmopConcept',
                                      'name': 'class_uri'}}})

    concept_id: Optional[int] = Field(default=None, description="""OMOP concept_id""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept', 'UnknownConcept']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept', 'UnknownConcept']} })
    class_uri: Literal["OmopConcept"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopConcept'} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })


class OmopEnum(OmopSemanticObject):
    """
    Enumeration of permissible values for a particular slot. This is intended to be used for defining slots that have a fixed set of permissible values, such as the staging axis (T, N, M, Group). This will not update dynamically with vocabulary updates, so should be used for concepts that are  short lists and not expected to change over time.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/omop_base',
         'slot_usage': {'class_uri': {'equals_string': 'OmopEnum',
                                      'name': 'class_uri'}}})

    enum_members: list[Concept] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopEnum']} })
    class_uri: Literal["OmopEnum"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopEnum'} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })


class OmopValueSet(OmopSemanticObject):
    """
    A semantic grouping of permissible values for a template slot. Members may be OmopConcepts, OmopGroups, or OmopEnums. This represents a registry-level value domain, not a direct OMOP structure.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/omop_base',
         'slot_usage': {'class_uri': {'equals_string': 'OmopValueSet',
                                      'name': 'class_uri'}}})

    members: Optional[list[OmopSemanticObject]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopValueSet']} })
    class_uri: Literal["OmopValueSet"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopValueSet'} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })


class Concept(ConfiguredBaseModel):
    """
    Concept that serves as a member of an OmopEnum. This is intended to be used for defining the permissible values of an OmopEnum, which is a fixed enumeration  of concepts that does not change dynamically with vocabulary updates.  The concept_id and label slots are used to specify the concept_id  and label of the concept that serves as a member of the enumeration.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/omop_base'})

    concept_id: Optional[int] = Field(default=None, description="""OMOP concept_id""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept', 'UnknownConcept']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept', 'UnknownConcept']} })


class UnknownCatalogue(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/omop_unknowns',
         'tree_root': True})

    unknowns: list[UnknownConcept] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['UnknownCatalogue']} })


class UnknownConcept(Concept):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://australiancancerdatanetwork.github.io/omop-semantics/schema/core/omop_unknowns',
         'slot_usage': {'concept_id': {'name': 'concept_id', 'required': True},
                        'label': {'identifier': True,
                                  'name': 'label',
                                  'required': True}}})

    label: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept', 'UnknownConcept']} })
    concept_id: int = Field(default=..., description="""OMOP concept_id""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept', 'UnknownConcept']} })
    reason: UnknownReason = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['UnknownConcept']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
OmopSemanticObject.model_rebuild()
OmopGroup.model_rebuild()
OmopConcept.model_rebuild()
OmopEnum.model_rebuild()
OmopValueSet.model_rebuild()
Concept.model_rebuild()
UnknownCatalogue.model_rebuild()
UnknownConcept.model_rebuild()
