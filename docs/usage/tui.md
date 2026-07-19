# TUI Explorer

Use the Textual-based TUI when you want to browse a compiled output-definition
catalogue, edit JSON input, run a projection, and inspect the result in one
terminal session.

## Install

The TUI dependencies are optional:

```bash
uv sync --extra dev
```

For a non-development install, install the package with its `tui` extra.

## Launch

```bash
omop-semantics tui
```

This launches the explorer against an empty runtime. The reusable app lives in
`omop_semantics.runtime.tui` and is mainly intended to be embedded by a caller
that already has concrete `OutputDefinition` instances to browse.

Programmatic use looks like:

```python
from omop_semantics.runtime import OmopSemanticEngine
from omop_semantics.runtime.tui import run_tui

engine = OmopSemanticEngine.from_yaml_paths(registry_paths=[], profile_paths=[])
runtime = engine.build_output_definition_runtime(my_definitions)
run_tui(runtime)
```

## What it shows

- A catalogue tree built from `describe_definition()`
- An editable JSON context pane
- A result tree using the same three-state language as the visualization HTML:
  green for projected rows, red for suppressed rows, amber for unresolved rows
  or links

For the meaning of those states, see [Visualization](../visualization.md).

## Controls

- `Ctrl+R` runs the selected definition against the JSON payload in the context pane
- `Q` quits the app

Selecting a definition in the tree loads a starter JSON payload into the
context pane. Child rows and annotations are browsable without changing the
current context. When the app is launched through `groundworkers --tui`, that
payload uses the flat `SemanticProjectionRequest` shape so it can be pasted
directly into the real worker-backed flow.
