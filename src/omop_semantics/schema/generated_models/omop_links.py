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
     'description': 'Linking tables and columns for CDM 5.4.2 event_field links.',
     'id': 'https://example.org/omop_semantics/links',
     'imports': ['linkml:types'],
     'name': 'omop_links',
     'prefixes': {'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'omop': {'prefix_prefix': 'omop',
                           'prefix_reference': 'https://athena.ohdsi.org/search-terms/terms/'}},
     'source_file': 'src/omop_semantics/schema/configuration/core/omop_links.yaml',
     'title': 'OMOP CDM Event Field Links'} )


class LinkMechanismCatalogue(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics/links', 'tree_root': True})

    link_mechanisms: list[LinkMechanism] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['LinkMechanismCatalogue']} })


class LinkMechanism(ConfiguredBaseModel):
    """
    A link that records a target row ID and the concept for its ID field.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics/links'})

    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['LinkMechanism']} })
    linking_table: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['LinkMechanism']} })
    event_id_column: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['LinkMechanism']} })
    field_concept_column: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['LinkMechanism']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
LinkMechanismCatalogue.model_rebuild()
LinkMechanism.model_rebuild()
