from omop_semantics.runtime import ConceptGroupAnchors
from omop_semantics.runtime.value_sets import RuntimeSemanticUnit


def accepts_concept_group_anchors(unit: RuntimeSemanticUnit) -> ConceptGroupAnchors:
    anchors: ConceptGroupAnchors = unit
    return anchors
