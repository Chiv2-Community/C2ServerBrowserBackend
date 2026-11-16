"""Generate separate Rust models and client crates from the authoritative OAS."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path

import yaml

from server_browser_codegen.generation import copy_resources, load_contract, run_generator


def resolve_component(spec: dict, value: dict) -> dict:
    if "$ref" in value:
        section, name = value["$ref"].split("/")[-2:]
        return spec["components"][section][name]
    return value


def operations(spec: dict) -> Iterator[tuple[dict, dict]]:
    for path in spec["paths"].values():
        for method, operation in path.items():
            if method in {"get", "post", "put", "delete", "patch", "head", "options"}:
                yield path, operation


def validate_capabilities(spec: dict) -> None:
    """Reject capabilities deliberately absent from the async Rust templates."""
    if spec.get("components", {}).get("securitySchemes") or spec.get("security"):
        raise ValueError("Rust client supports explicit credential headers, not security schemes")

    def check_schema(schema: dict) -> None:
        if schema.get("type") == "file" or schema.get("format") in {"binary", "byte"}:
            raise ValueError("Rust client does not support binary/file schemas")
        for value in schema.values():
            if isinstance(value, dict):
                check_schema(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        check_schema(item)

    check_schema(spec.get("components", {}).get("schemas", {}))
    for path, operation in operations(spec):
        if operation.get("security"):
            raise ValueError("Rust client does not support security schemes")
        if any(key in {
            "x-group-parameters", "x-rust-group-parameters", "x-use-async-file-stream",
        } for key in operation):
            raise ValueError("Unsupported Rust generator option")
        for parameter in [*path.get("parameters", []), *operation.get("parameters", [])]:
            parameter = resolve_component(spec, parameter)
            schema = resolve_component(spec, parameter.get("schema", {}))
            check_schema(schema)
            if parameter.get("in") not in {"query", "path", "header"} or schema.get("type") not in {"string", "integer", "number", "boolean"}:
                raise ValueError("Rust client supports scalar query/path/header parameters only")
            if parameter["in"] == "path" and (not parameter.get("required") or schema.get("nullable")):
                raise ValueError("Rust path parameters must be required and nonnullable")
        for media, content in resolve_component(spec, operation.get("requestBody", {})).get("content", {}).items():
            if media != "application/json":
                raise ValueError(f"Unsupported Rust request media type: {media}")
            check_schema(content.get("schema", {}))
        success_schemas = []
        for status, response in operation["responses"].items():
            for media, content in resolve_component(spec, response).get("content", {}).items():
                schema = resolve_component(spec, content.get("schema", {}))
                if str(status).startswith("2"):
                    success_schemas.append(schema)
                check_schema(schema)
                if media != "application/json" and not media.endswith("+json") and not (
                    media in {"text/plain", "text/yaml", "application/yaml", "application/x-yaml"}
                    and schema.get("type") == "string"
                ):
                    raise ValueError(f"Unsupported Rust response media type: {media}")
                if not str(status).startswith("2") and media != "application/json" and not media.endswith("+json"):
                    raise ValueError("Rust error responses must be JSON")
        if success_schemas and any(schema != success_schemas[0] for schema in success_schemas):
            raise ValueError("Rust client requires one successful response schema per operation")


def normalize_text_responses(spec: dict) -> None:
    for _, operation in operations(spec):
        contents = [
            (media, resolve_component(spec, content["schema"]))
            for status, response in operation["responses"].items()
            if str(status).startswith("2")
            for media, content in resolve_component(spec, response).get("content", {}).items()
        ]
        # Returning raw text is safe only when every success has a string type.
        if contents and all(schema.get("type") == "string" for _, schema in contents):
            operation["x-rust-text-media-types"] = [
                media for media, _ in contents
                if media != "application/json" and not media.endswith("+json")
            ]


def normalize_anyof(schemas: dict) -> None:
    def required_fields(definition: dict) -> set[str]:
        if "$ref" in definition:
            return required_fields(schemas[definition["$ref"].rsplit("/", 1)[1]])
        fields = set(definition.get("required", []))
        for member in definition.get("allOf", []):
            fields.update(required_fields(member))
        return fields

    def rust_name(name: str) -> str:
        words = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", words)
        return "".join(word.title() for word in words.split("_"))

    for definition in schemas.values():
        if "anyOf" in definition:
            definition["anyOf"].sort(
                key=lambda item: len(required_fields(item)), reverse=True
            )
            definition["x-rust-anyof-variants"] = [
                {"name": rust_name(item["$ref"].rsplit("/", 1)[1])}
                for item in definition["anyOf"]
            ]


def generated_files(directory: Path) -> set[Path]:
    return {
        path.relative_to(directory) for path in (directory / "src").rglob("*.rs")
    } | ({Path("Cargo.toml")} if (directory / "Cargo.toml").is_file() else set())


def sync_package(source: Path, target: Path, check: bool) -> None:
    expected, actual = generated_files(source), generated_files(target)
    if check:
        if expected != actual or any(
            (source / path).read_bytes() != (target / path).read_bytes()
            for path in expected & actual
        ):
            raise SystemExit(f"Generated Rust {target.name} is stale or hand-edited")
    else:
        for obsolete in actual - expected:
            (target / obsolete).unlink()
        for path in expected:
            (target / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / path, target / path)


def generate(root: Path, check: bool = False) -> None:
    _, spec = load_contract(root)
    validate_capabilities(spec)
    normalize_anyof(spec["components"]["schemas"])
    normalize_text_responses(spec)
    with tempfile.TemporaryDirectory(prefix="server-browser-rust-") as temporary:
        directory = Path(temporary)
        templates = directory / "templates"
        copy_resources(
            files("server_browser_codegen").joinpath("templates/rust"), templates
        )
        for alias, owner in (
            ("Cargo", "client"),
            ("lib", "client"),
            ("model", "models"),
        ):
            shutil.copyfile(
                templates / owner / f"{alias}.mustache", templates / f"{alias}.mustache"
            )
        schema = directory / "schema.yaml"
        schema.write_text(yaml.safe_dump(spec, sort_keys=False))
        config = directory / "config.yaml"
        config.write_text(
            yaml.safe_dump(
                {
                    "files": {
                        "models/Cargo.mustache": {
                            "destinationFilename": "models-package/Cargo.toml"
                        },
                        "models/lib.mustache": {
                            "destinationFilename": "models-package/src/lib.rs"
                        },
                    }
                }
            )
        )
        output = directory / "output"
        run_generator(
            [
                "-g",
                "rust",
                "-i",
                str(schema),
                "-o",
                str(output),
                "-t",
                str(templates),
                "-c",
                str(config),
                "--additional-properties=packageName=server-browser-client,packageVersion=1.0.0,supportAsync=true,avoidBoxedModels=true",
                "--global-property=apiDocs=false,modelDocs=false,apiTests=false,modelTests=false",
            ],
            root,
        )
        models = output / "models-package"
        shutil.move(str(output / "src/models"), models / "src/models")
        for name, source in (("models", models), ("client", output)):
            for path in generated_files(source):
                text = (source / path).read_text()
                (source / path).write_text(
                    "\n".join(
                        line.rstrip() for line in text.splitlines()
                    ).strip()
                    + "\n"
                )
            subprocess.run(
                ["rustfmt", "--edition", "2021", str(source / "src/lib.rs")],
                cwd=root,
                check=True,
            )
            sync_package(source, root / f"sdk/rust/server-browser-{name}", check)
    print(
        "Generated Rust models and client are current."
        if check
        else "Generated Rust models and client."
    )
