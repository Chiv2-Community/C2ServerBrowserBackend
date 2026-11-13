"""Verify drift detection without editing real generated sources."""
from pathlib import Path

import pytest
import yaml

from server_browser_codegen import generation


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


def test_generated_drift_check_ignores_build_resources(tmp_path):
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    (expected / "contract.json").write_text("{}")
    (actual / "openapi.yaml").write_text("stale build output")
    assert generation.same_sources(expected, actual)


def test_generated_drift_check_ignores_bytecode_but_compares_nested_sources(tmp_path):
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    for directory in (expected, actual):
        (directory / "models").mkdir(parents=True)
        (directory / "models/model.py").write_text("generated\n")
    (actual / "models/__pycache__").mkdir()
    (actual / "models/__pycache__/model.pyc").write_bytes(b"bytecode")
    assert generation.same_sources(expected, actual)
    (actual / "models/model.py").write_text("hand edit\n")
    assert not generation.same_sources(expected, actual)


def test_templates_are_scoped_to_their_output_package(tmp_path):
    root = tmp_path / "repository with spaces"
    config_path = generation.prepare_config(root, tmp_path / "staged")
    config = yaml.safe_load(config_path.read_text())
    templates = Path(config["templateDir"])
    assert config["inputSpec"] == str(root / "assets/chiv2-server-browser-api.yaml")
    for name, declaration in config["files"].items():
        owner = name.split("/", 1)[0]
        assert (templates / name).is_file()
        if owner != "shared":
            assert declaration["destinationFilename"].startswith(f"src/server_browser_{owner}/")
    for alias, source in generation.ENTRYPOINTS.items():
        assert (templates / alias).read_bytes() == (templates / source).read_bytes()


def test_cli_reports_a_missing_repository_contract(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        generation.main(["--root", str(tmp_path), "--check"])
    assert error.value.code == 2
    assert "pass --root" in capsys.readouterr().err


def test_cli_passes_explicit_root_and_check_to_generation(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/chiv2-server-browser-api.yaml").write_text("{}")
    calls = []
    monkeypatch.setattr(generation, "generate", lambda root, check: calls.append((root, check)))
    generation.main(["--root", str(tmp_path), "--check"])
    assert calls == [(tmp_path.resolve(), True)]
