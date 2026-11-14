"""Generate the API package with the pinned OpenAPI Generator toolchain."""

from __future__ import annotations

import argparse
import ast
import filecmp
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

import yaml
from openapi_spec_validator import validate

PACKAGES = ("models", "server", "fastapi", "client")
BUILD_RESOURCES = {Path("contract.json"), Path("openapi.yaml")}
ENTRYPOINTS = {
    "model.mustache": "models/model.mustache",
    "base_api.mustache": "server/base_api.mustache",
    "api.mustache": "fastapi/api.mustache",
}


def require_local_references(value: object) -> None:
    if isinstance(value, dict):
        reference = value.get("$ref")
        if reference is not None and not reference.startswith("#/components/"):
            raise ValueError(
                "Use local component references; remote schema retrieval is disabled"
            )
        for child in value.values():
            require_local_references(child)
    elif isinstance(value, list):
        for child in value:
            require_local_references(child)


def source_files(directory: Path) -> set[Path]:
    return {
        path.relative_to(directory)
        for path in directory.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    } - BUILD_RESOURCES


def same_sources(left: Path, right: Path) -> bool:
    if not right.is_dir():
        return False
    left_files = source_files(left)
    right_files = source_files(right)
    return left_files == right_files and all(
        filecmp.cmp(left / p, right / p, shallow=False) for p in left_files
    )


def copy_resources(source: Traversable, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            copy_resources(child, target)
        else:
            target.write_bytes(child.read_bytes())


def prepare_config(root: Path, directory: Path) -> Path:
    resources = files("server_browser_codegen")
    templates = directory / "templates"
    copy_resources(resources.joinpath("templates"), templates)
    # OpenAPI Generator requires these three entry-point filenames at its template root.
    # Supporting templates retain their module-scoped paths from config.yaml.
    for name, source in ENTRYPOINTS.items():
        shutil.copyfile(templates / source, templates / name)
    config = yaml.safe_load(resources.joinpath("config.yaml").read_text())
    config["inputSpec"] = str(root / "assets/chiv2-server-browser-api.yaml")
    config["templateDir"] = str(templates)
    path = directory / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return path


def prepare_packages(output: Path, spec: dict, contract_text: str) -> None:
    """Partition generator output into the four SDK packages and normalize sources."""
    generated = output / "src/server_browser_models"
    # Keep the contract/bindings, not the generator's example application.
    for source in generated.rglob("*"):
        relative = source.relative_to(generated)
        if source.is_file() and not (
            relative.parts[0] in ("models", "apis")
            or relative.as_posix() in ("__init__.py", "runtime.py", "py.typed")
        ):
            source.unlink()
    (generated / "models/extra_models.py").unlink(missing_ok=True)
    (generated / "contract.json").write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n"
    )
    (generated / "openapi.yaml").write_text(contract_text)
    server = output / "src/server_browser_server"
    adapter = output / "src/server_browser_fastapi"
    for source in (generated / "apis").glob("*.py"):
        destination = server if source.name.endswith("_base.py") else adapter
        (destination / "apis").mkdir(exist_ok=True)
        source.rename(destination / "apis" / source.name)
    (generated / "apis").rmdir()
    for name in PACKAGES:
        package = output / f"src/server_browser_{name}"
        (package / "py.typed").write_text("")
        if (package / "apis").is_dir():
            (package / "apis/__init__.py").write_text("")
    for source in (output / "src").rglob("*.py"):
        text = source.read_text().rstrip()
        ast.parse(text, filename=str(source))
        source.write_text(text + "\n" if text else "")


def load_contract(root: Path) -> tuple[str, dict]:
    text = (root / "assets/chiv2-server-browser-api.yaml").read_text()
    spec = yaml.safe_load(text)
    require_local_references(spec)
    validate(spec)
    operations = [
        operation
        for path in spec["paths"].values()
        for method, operation in path.items()
        if method in {"get", "put", "post", "delete", "patch", "options", "head"}
    ]
    ids = [operation.get("operationId") for operation in operations]
    if None in ids or len(set(ids)) != len(ids):
        raise ValueError("Each API operation must declare a unique operationId")
    if any(len(operation.get("tags", [])) != 1 for operation in operations):
        raise ValueError(
            "Each API operation must declare exactly one handler-interface tag"
        )
    return text, spec


def generate(root: Path, check: bool = False) -> None:
    root = root.resolve()
    text, spec = load_contract(root)
    with tempfile.TemporaryDirectory(prefix="server-browser-codegen-") as directory:
        temporary = Path(directory)
        config = prepare_config(root, temporary)
        output = temporary / "generated"
        process = subprocess.run(
            [
                sys.executable,
                "-c",
                "from openapi_generator_cli import cli; cli()",
                "generate",
                "-c",
                str(config),
                "-o",
                str(output),
                "--global-property",
                "models,apis,supportingFiles,modelDocs=false,modelTests=false,apiDocs=false,apiTests=false",
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if process.returncode:
            print(process.stdout, file=sys.stderr)
            print(process.stderr, file=sys.stderr)
            process.check_returncode()
        prepare_packages(output, spec, text)
        for name in PACKAGES:
            source = output / f"src/server_browser_{name}"
            target = root / f"sdk/python/server-browser-{name}/src/server_browser_{name}"
            if check:
                if not same_sources(source, target):
                    raise SystemExit(
                        f"Generated {name} is stale or hand-edited; run uv run server-browser-codegen"
                    )
            else:
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(source, target)
        print(
            "Generated API is current."
            if check
            else "Generated models, server, FastAPI adapter, and client."
        )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root containing assets/ and sdk/ (default: current directory)",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--language", choices=("python", "rust", "all"), default="all")
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    if not (root / "assets/chiv2-server-browser-api.yaml").is_file():
        parser.error("Repository contract not found; pass --root /path/to/repository")
    if arguments.language in ("python", "all"):
        generate(root, arguments.check)
    if arguments.language in ("rust", "all"):
        from server_browser_codegen.rust import generate as generate_rust

        generate_rust(root, arguments.check)
