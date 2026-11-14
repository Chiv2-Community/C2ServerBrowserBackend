"""Rust output boundaries and nonmutating generation drift checks."""

from importlib.resources import files
from pathlib import Path

import pytest

from server_browser_codegen import generation, rust


def test_operation_traversal_skips_path_metadata_and_preserves_parent():
    operation = {"responses": {}}
    path = {
        "summary": "Path metadata",
        "parameters": [],
        "x-extra": {},
        **{method: operation for method in (
            "get", "post", "put", "delete", "patch", "head", "options",
        )},
    }
    found = list(rust.operations({"paths": {"/servers": path}}))
    assert len(found) == 7
    assert all(parent is path and child is operation for parent, child in found)
    rust.validate_capabilities({"paths": {"/servers": path}})
    rust.normalize_text_responses({"paths": {"/servers": path}})


def test_text_decoding_comes_from_declared_success_media_types():
    def operation(schema):
        return {"responses": {"200": {"content": {"text/yaml": {"schema": schema}}}}}

    spec = {"paths": {"/text": {"get": operation({"type": "string"})},
                      "/model": {"get": operation({"$ref": "#/components/schemas/Model"})}},
            "components": {"schemas": {"Model": {"type": "object"}}}}
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


def test_rust_stages_owned_templates_without_rewriting(tmp_path, monkeypatch):
    resources = files("server_browser_codegen").joinpath("templates/rust")
    aliases = {"Cargo": "client", "lib": "client", "model": "models"}
    checked = []

    class Staged(Exception):
        pass

    def inspect_templates(arguments, root):
        assert root == tmp_path
        options = next(arg for arg in arguments if arg.startswith("--additional-properties="))
        assert "supportAsync=true" in options
        assert "supportAsync=false" not in options
        templates = Path(arguments[arguments.index("-t") + 1])
        expected = tmp_path / "expected"
        generation.copy_resources(resources, expected)
        for source in expected.rglob("*"):
            if source.is_file():
                relative = source.relative_to(expected)
                assert (templates / relative).read_bytes() == source.read_bytes()
                checked.append(relative.as_posix())
        for alias, owner in aliases.items():
            assert (templates / f"{alias}.mustache").read_bytes() == (
                expected / owner / f"{alias}.mustache"
            ).read_bytes()
        assert not (templates / "model-default.mustache").exists()
        raise Staged

    monkeypatch.setattr(rust, "load_contract", lambda root: (
        "", {"paths": {}, "components": {"schemas": {}}},
    ))
    monkeypatch.setattr(rust, "run_generator", inspect_templates)
    with pytest.raises(Staged):
        rust.generate(tmp_path, check=True)
    assert {"models/model-default.mustache", "reqwest/api.mustache",
            "UPSTREAM.md", "LICENSE.apache-2.0"} <= set(checked)


@pytest.mark.parametrize("media", ["multipart/form-data", "application/x-www-form-urlencoded", "application/octet-stream", "text/plain", "application/custom+json"])
def test_rust_rejects_unsupported_request_media(media):
    spec = {"paths": {"/upload": {"post": {
        "requestBody": {"content": {media: {"schema": {"type": "string"}}}},
        "responses": {},
    }}}}
    with pytest.raises(ValueError, match="request media"):
        rust.validate_capabilities(spec)


@pytest.mark.parametrize("schema", [
    {"type": "string", "format": "binary"},
    {"type": "string", "format": "byte"},
    {"type": "file"},
    {"type": "object", "properties": {"data": {"type": "string", "format": "binary"}}},
])
def test_rust_rejects_binary_schemas(schema):
    spec = {"paths": {}, "components": {"schemas": {"Unsupported": schema}}}
    with pytest.raises(ValueError, match="binary/file"):
        rust.validate_capabilities(spec)


@pytest.mark.parametrize("media,schema,status", [
    ("application/octet-stream", {"type": "string"}, "200"),
    ("text/yaml", {"type": "object"}, "200"),
    ("text/plain", {"type": "string"}, "400"),
])
def test_rust_rejects_unsupported_responses(media, schema, status):
    spec = {"paths": {"/response": {"get": {"responses": {
        status: {"content": {media: {"schema": schema}}},
    }}}}}
    with pytest.raises(ValueError, match="response"):
        rust.validate_capabilities(spec)


def test_rust_rejects_security_schemes_and_complex_parameters():
    with pytest.raises(ValueError, match="security schemes"):
        rust.validate_capabilities({"components": {"securitySchemes": {"OAuth": {"type": "oauth2"}}}})
    for location, schema in [("query", {"type": "array"}), ("cookie", {"type": "string"})]:
        with pytest.raises(ValueError, match="scalar query/path/header"):
            rust.validate_capabilities({"paths": {"/query": {"get": {
                "parameters": [{"in": location, "schema": schema}], "responses": {},
            }}}})


def test_rust_rejects_unsupported_options_before_generator(tmp_path, monkeypatch):
    spec = {"paths": {"/option": {"get": {"x-group-parameters": True, "responses": {}}}}}
    monkeypatch.setattr(rust, "load_contract", lambda root: ("", spec))
    monkeypatch.setattr(rust, "run_generator", lambda *args: pytest.fail("generator invoked"))
    with pytest.raises(ValueError, match="generator option"):
        rust.generate(tmp_path)


def test_rust_templates_have_no_removed_capabilities():
    resources = files("server_browser_codegen").joinpath("templates/rust")
    text = "\n".join(resources.joinpath(path).read_text() for path in [
        "reqwest/api.mustache", "reqwest/configuration.mustache",
        "client/response.mustache", "client/text_response.mustache", "client/Cargo.mustache",
    ])
    for removed in ["blocking", "supportAsync", "AWSV4", "multipart", "FramedRead", "token_source", "api_key", "oauth_access_token"]:
        assert removed not in text


def test_rust_resolves_declared_text_components_and_rejects_mixed_success_schemas():
    spec = {
        "components": {
            "schemas": {"Text": {"type": "string"}},
            "responses": {"Yaml": {"content": {
                "text/yaml": {"schema": {"$ref": "#/components/schemas/Text"}},
            }}},
        },
        "paths": {"/yaml": {"get": {"responses": {
            "200": {"$ref": "#/components/responses/Yaml"},
        }}}},
    }
    rust.validate_capabilities(spec)
    rust.normalize_text_responses(spec)
    operation = spec["paths"]["/yaml"]["get"]
    assert operation["x-rust-text-media-types"] == ["text/yaml"]
    operation["responses"]["201"] = {"content": {
        "application/json": {"schema": {"type": "object"}},
    }}
    with pytest.raises(ValueError, match="one successful response schema"):
        rust.validate_capabilities(spec)
