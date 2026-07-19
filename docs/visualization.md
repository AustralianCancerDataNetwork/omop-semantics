# Visualization

Use `omop_semantics.runtime.viz` when you need to understand one deterministic
projection result or inspect the structure of an output-definition catalogue
without reading raw JSON by hand.

The runtime exposes four helpers:

- `bundle_to_mermaid(bundle)` returns Mermaid flowchart text for one projected bundle.
- `bundle_to_html(bundle)` wraps that Mermaid source in a single HTML page that loads Mermaid from a CDN at view time.
- `catalogue_to_mermaid(runtime)` renders one or more compiled output definitions as a structural authoring view.
- `catalogue_to_html(runtime)` wraps the catalogue diagram in the same browser-ready HTML shell.

The generated HTML is a single file, but it is not fully self-contained: it
loads Mermaid from a CDN when viewed. If network access or notebook content
security policy blocks that script, the page still shows the raw Mermaid source
inside the `<pre class="mermaid">` block.

## Visual states

The Mermaid renderer uses the same three states everywhere:

| State | Meaning |
|---|---|
| `ok` | A row was projected successfully. |
| `suppressed` | The definition matched, but the row was dropped deterministically by a `DerivationRule` or `SpecialValuePolicy`. |
| `unresolved` | The definition structure matched, but required row fields or link endpoints were missing. |

## Bundle example: projected row kept

```python
from pathlib import Path

from omop_semantics.runtime import (
    ContextFieldRef,
    DerivationRule,
    OmopSemanticEngine,
    OutputDefinition,
    OutputRowProjection,
    bundle_to_html,
)

engine = OmopSemanticEngine.from_yaml_paths(registry_paths=[], profile_paths=[])

definition = OutputDefinition(
    name="condition_with_status_from_secondary_field",
    role="condition_modifier",
    row_projections=(
        OutputRowProjection(
            row_id="condition",
            profile_name="condition_with_status",
            field_bindings={
                "condition_concept_id": ContextFieldRef("grounded.concept_id"),
            },
        ),
    ),
    derivation_rules=(
        DerivationRule(
            target_row="condition",
            target_slot="condition_status_concept_id",
            source_field=ContextFieldRef("source.role_field"),
            code_map={"1": 32902, "2": 32908},
            suppress_codes=frozenset({"3"}),
        ),
    ),
)

runtime = engine.build_output_definition_runtime([definition])
bundle = runtime.project(
    "condition_with_status_from_secondary_field",
    {"grounded": {"concept_id": 4152280}, "source": {"role_field": "1"}},
)

html = bundle_to_html(bundle, title="Role = Primary (kept)")
Path("role_primary_kept.html").write_text(html.raw, encoding="utf-8")
```

Opening the saved file in a browser shows a green `condition` node with the
resolved `condition_status_concept_id`.

## Bundle example: row suppressed

The same definition, run with `role_field = "3"`, produces no projected rows and
one red dashed suppression node explaining why nothing was written:

```python
bundle = runtime.project(
    "condition_with_status_from_secondary_field",
    {"grounded": {"concept_id": 4152280}, "source": {"role_field": "3"}},
)

html = bundle_to_html(bundle, title="Role = Non-contributing (suppressed)")
Path("role_non_contributing.html").write_text(html.raw, encoding="utf-8")
```

Suppressed rows are never omitted silently. The diagram surfaces the source
field, source code, and deterministic reason directly on the node.

## Catalogue example

Use the catalogue view to understand authoring structure rather than one
execution result:

```python
from omop_semantics.runtime import (
    ContextFieldRef,
    OutputDefinition,
    OutputRowProjection,
    SpecialValuePolicy,
    catalogue_to_html,
)

criteria_gate_condition = OutputDefinition(
    name="criteria_gate_condition",
    role="condition_modifier",
    row_projections=(
        OutputRowProjection(
            row_id="condition",
            profile_name="condition_simple",
            field_bindings={
                "condition_concept_id": ContextFieldRef("grounded.concept_id"),
            },
            special_value_policy=SpecialValuePolicy(
                source_field=ContextFieldRef("source.raw_value"),
                allowed_special_values=frozenset({"0"}),
                suppression_mode="drop",
            ),
        ),
    ),
)

combined_runtime = engine.build_output_definition_runtime(
    [definition, criteria_gate_condition]
)
html = catalogue_to_html(combined_runtime, title="Output Definition Catalogue")
Path("catalogue.html").write_text(html.raw, encoding="utf-8")
```

The catalogue diagram renders row projections, link rules, derivation-rule
inputs, and suppression annotations without requiring a concrete input context.

## Notebook use

Inline notebook display via `IPython.display.HTML(html.raw)` is convenient, but
it is best-effort only. Browser viewing of the saved `.html` file is the
guaranteed path across notebook front ends and local environments.

## Interactive exploration

For a terminal-based browse/edit/run loop, use the Textual explorer documented
in [TUI Explorer](usage/tui.md).
