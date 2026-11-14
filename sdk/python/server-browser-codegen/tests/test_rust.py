"""Rust output boundaries and nonmutating generation drift checks."""

import pytest

from server_browser_codegen import generation, rust


def test_text_decoding_comes_from_declared_success_media_types():
    def operation(schema):
        return {"responses": {"200": {"content": {"text/yaml": {"schema": schema}}}}}

    spec = {"paths": {"/text": {"get": operation({"type": "string"})},
                      "/model": {"get": operation({"$ref": "#/components/schemas/Model"})}}}
    rust.normalize_text_responses(spec)
    assert spec["paths"]["/text"]["get"]["x-rust-text-media-types"] == ["text/yaml"]
    assert "x-rust-text-media-types" not in spec["paths"]["/model"]["get"]


def test_text_decoding_does_not_bypass_json_or_mixed_success_types():
    json_string = {"responses": {"200": {"content": {
        "application/json": {"schema": {"type": "string"}},
        "application/custom+json": {"schema": {"type": "string"}},
    }}}}
    mixed = {"responses": {"200": {"content": {
        "text/plain": {"schema": {"type": "string"}},
        "application/json": {"schema": {"type": "object"}},
    }}}}
    spec = {"paths": {"/json": {"get": json_string}, "/mixed": {"get": mixed}}}
    rust.normalize_text_responses(spec)
    assert json_string["x-rust-text-media-types"] == []
    assert "x-rust-text-media-types" not in mixed


def test_anyof_orders_by_inherited_required_fields():
    schemas = {
        "Base": {"required": ["name"]},
        "Diagnostic": {
            "allOf": [{"$ref": "#/components/schemas/Base"}, {"required": ["ip"]}]
        },
        "Entry": {
            "anyOf": [
                {"$ref": "#/components/schemas/Base"},
                {"$ref": "#/components/schemas/Diagnostic"},
            ]
        },
    }
    rust.normalize_anyof(schemas)
    assert schemas["Entry"]["x-rust-anyof-variants"] == [
        {"name": "Diagnostic"},
        {"name": "Base"},
    ]


def test_rust_sync_detects_missing_edited_extra_sources_without_touching_tests(
    tmp_path,
):
    source, target = tmp_path / "source", tmp_path / "target"
    (source / "src").mkdir(parents=True)
    (source / "Cargo.toml").write_text("manifest")
    (source / "src/lib.rs").write_text("generated")
    with pytest.raises(SystemExit, match="stale"):
        rust.sync_package(source, target, True)
    rust.sync_package(source, target, False)
    rust.sync_package(source, target, True)
    (target / "src/lib.rs").write_text("edited")
    with pytest.raises(SystemExit, match="stale"):
        rust.sync_package(source, target, True)
    assert (target / "src/lib.rs").read_text() == "edited"
    rust.sync_package(source, target, False)
    (target / "src/extra.rs").write_text("extra")
    (target / "tests").mkdir()
    (target / "tests/contract.rs").write_text("owned test")
    with pytest.raises(SystemExit, match="stale"):
        rust.sync_package(source, target, True)
    rust.sync_package(source, target, False)
    assert not (target / "src/extra.rs").exists()
    assert (target / "tests/contract.rs").read_text() == "owned test"


@pytest.mark.parametrize(
    "language,expected",
    [("all", ["python", "rust"]), ("python", ["python"]), ("rust", ["rust"])],
)
def test_cli_language_selection(tmp_path, monkeypatch, language, expected):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/chiv2-server-browser-api.yaml").write_text("{}")
    calls = []
    monkeypatch.setattr(
        generation, "generate", lambda root, check: calls.append("python")
    )
    monkeypatch.setattr(rust, "generate", lambda root, check: calls.append("rust"))
    generation.main(["--root", str(tmp_path), "--check", "--language", language])
    assert calls == expected


def test_rust_only_rejects_external_references_before_generation(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/chiv2-server-browser-api.yaml").write_text(
        '$ref: "https://example.invalid/schema"'
    )
    with pytest.raises(ValueError, match="local component"):
        rust.generate(tmp_path)
