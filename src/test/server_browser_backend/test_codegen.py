"""Verify drift detection without editing real generated sources."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("generate_api", ROOT / "scripts/generate_api.py")
assert spec is not None and spec.loader is not None
generation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generation)


def test_generated_drift_check_detects_missing_extra_and_edited_files(tmp_path):
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    (expected / "model.py").write_text("generated\n")
    assert not generation.same_sources(expected, actual)
    (actual / "model.py").write_text("generated\n")
    assert generation.same_sources(expected, actual)
    (actual / "model.py").write_text("hand edit\n")
    assert not generation.same_sources(expected, actual)
    (actual / "model.py").write_text("generated\n")
    (actual / "extra.py").write_text("extra\n")
    assert not generation.same_sources(expected, actual)


@pytest.mark.parametrize("reference", ["https://example.invalid/schema.json", "file:///etc/passwd"])
def test_codegen_rejects_external_references(reference):
    with pytest.raises(ValueError, match="local component"):
        generation.require_local_references({"schema": [{"$ref": reference}]})


def test_codegen_accepts_local_component_references():
    generation.require_local_references({"schema": {"$ref": "#/components/schemas/LoginRequest"}})
