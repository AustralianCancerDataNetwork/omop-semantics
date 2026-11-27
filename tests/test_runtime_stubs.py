from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from omop_semantics.runtime.default_valuesets import runtime

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_runtime_stubs import OUTPUT, render_stub, runtime_paths  # noqa: E402


def test_default_runtime_stub_is_up_to_date() -> None:
    assert OUTPUT.read_text() == render_stub(), (
        "default_valuesets.pyi is out of date; regenerate it with: "
        "uv run python scripts/generate_runtime_stubs.py"
    )


def test_every_stubbed_runtime_path_exists_with_its_declared_type() -> None:
    for path, expected_type in runtime_paths():
        value = runtime
        for name in path:
            value = getattr(value, name)
        assert isinstance(value, expected_type), (
            f"runtime.{'.'.join(path)} is {type(value).__name__}, "
            f"expected {expected_type.__name__}"
        )


def test_misspelled_runtime_names_fail_ty(tmp_path: Path) -> None:
    # Each typo is used in a context that accepts any type, so ty can only
    # fail by reporting the attribute itself as unresolved.
    typos = {
        "typo_valueset": "runtime.typo_valueset",
        "typo_unit": "runtime.types.typo_unit",
        "episode_of_crae": "runtime.types.disease_episode_types.episode_of_crae",
    }
    probe = tmp_path / "invalid_runtime_names.py"
    probe.write_text(
        "from omop_semantics.runtime.default_valuesets import runtime\n"
        + "".join(f"print({path})\n" for path in typos.values())
    )
    result = subprocess.run(
        [sys.executable, "-m", "ty", "check", "--output-format", "concise", str(probe)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0, f"ty accepted misspelled runtime names:\n{output}"
    for name in typos:
        assert any(
            "unresolved-attribute" in line and name in line
            for line in output.splitlines()
        ), f"ty did not report {name} as unresolved:\n{output}"
