"""Generate separate Rust models and client crates from the authoritative OAS."""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from importlib.resources import files
from pathlib import Path

import openapi_generator_cli
import yaml

from server_browser_codegen.generation import copy_resources, load_contract, run_generator


def normalize_text_responses(spec: dict) -> None:
    for path in spec["paths"].values():
        for method, operation in path.items():
            if method not in {"get", "post", "put", "delete", "patch", "head", "options"}:
                continue
            contents = [
                (media, content["schema"])
                for status, response in operation["responses"].items()
                if str(status).startswith("2")
                for media, content in response.get("content", {}).items()
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
        jar = Path(openapi_generator_cli.__file__).parent / "openapi-generator.jar"
        with zipfile.ZipFile(jar) as archive:
            (templates / "model-default.mustache").write_bytes(
                archive.read("rust/model.mustache")
            )
            # Stage the pinned upstream API template with a module-owned text hook.
            api = archive.read("rust/reqwest/api.mustache").decode()
            marker = "    let content_type = super::ContentType::from(content_type);"
            if api.count(marker) != 1:
                raise ValueError("Pinned Rust API template text-response hook changed")
            (templates / "reqwest").mkdir()
            (templates / "reqwest/api.mustache").write_text(
                api.replace(marker, "{{>client/text_response}}\n" + marker)
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
                "--additional-properties=packageName=server-browser-client,packageVersion=1.0.0,supportAsync=false,avoidBoxedModels=true",
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
                    "\n".join(line.rstrip() for line in text.splitlines()).strip()
                    + "\n"
                )
            sync_package(source, root / f"sdk/rust/server-browser-{name}", check)
    print(
        "Generated Rust models and client are current."
        if check
        else "Generated Rust models and client."
    )
