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
from pathlib import Path

import yaml
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("models", "server", "fastapi", "client")
BUILD_RESOURCES = {Path("contract.json"), Path("openapi.yaml")}


def require_local_references(value: object) -> None:
    if isinstance(value, dict):
        reference = value.get("$ref")
        if reference is not None and not reference.startswith("#/components/"):
            raise ValueError("Use local component references; remote schema retrieval is disabled")
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
    return left_files == right_files and all(filecmp.cmp(left / p, right / p, shallow=False) for p in left_files)


def generate(check: bool) -> None:
    text = (ROOT / "assets/chiv2-server-browser-api.yaml").read_text()
    spec = yaml.safe_load(text)
    require_local_references(spec)
    validate(spec)
    operations = [operation for path in spec["paths"].values() for method, operation in path.items() if method in {"get", "put", "post", "delete", "patch", "options", "head"}]
    ids = [operation.get("operationId") for operation in operations]
    if None in ids or len(set(ids)) != len(ids):
        raise ValueError("Each API operation must declare a unique operationId")
    if any(len(operation.get("tags", [])) != 1 for operation in operations):
        raise ValueError("Each API operation must declare exactly one handler-interface tag")
    with tempfile.TemporaryDirectory(prefix="server-browser-codegen-") as directory:
        output = Path(directory)
        process = subprocess.run([
            sys.executable, "-c", "from openapi_generator_cli import cli; cli()",
            "generate", "-c", "codegen/config.yaml", "-o", str(output),
            "--global-property", "models,apis,supportingFiles,modelDocs=false,modelTests=false,apiDocs=false,apiTests=false",
        ], cwd=ROOT, capture_output=True, text=True)
        if process.returncode:
            print(process.stdout, file=sys.stderr)
            print(process.stderr, file=sys.stderr)
            process.check_returncode()
        generated = output / "src/server_browser_models"
        # Keep the contract/bindings, not the generator's example application.
        for source in list(generated.rglob("*")):
            if source.is_file() and not (
                source.relative_to(generated).parts[0] in ("models", "apis")
                or source.relative_to(generated).as_posix() in ("__init__.py", "runtime.py", "py.typed")
            ):
                source.unlink()
        (generated / "models/extra_models.py").unlink(missing_ok=True)
        (generated / "contract.json").write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
        (generated / "openapi.yaml").write_text(text)
        server = output / "src/server_browser_server"
        adapter = output / "src/server_browser_fastapi"
        for source in (generated / "apis").glob("*.py"):
            destination = server if source.name.endswith("_base.py") else adapter
            (destination / "apis").mkdir(exist_ok=True)
            source.rename(destination / "apis" / source.name)
        (generated / "apis").rmdir()
        for name in PACKAGES:
            package = output / f"src/server_browser_{name}"
            if name != "models":
                exports = '"""Generated API support. DO NOT EDIT."""\n'
                if name == "client":
                    exports += "from .client import Client as Client, AsyncClient as AsyncClient\n"
                    exports += "from .runtime import ClientResponse as ClientResponse, ClientDecodeError as ClientDecodeError\n"
                if name == "server":
                    exports += "from .runtime import ApiResponse as ApiResponse, RequestContext as RequestContext\n"
                (package / "__init__.py").write_text(exports)
                (package / "py.typed").write_text("")
            if (package / "apis").is_dir():
                (package / "apis/__init__.py").write_text("")
        for source in (output / "src").rglob("*.py"):
            text = source.read_text().rstrip()
            source.write_text(text + "\n" if text else "")
            ast.parse(text, filename=str(source))
        for name in PACKAGES:
            source = output / f"src/server_browser_{name}"
            target = ROOT / f"packages/server-browser-{name}/src/server_browser_{name}"
            if check:
                if not same_sources(source, target):
                    raise SystemExit(f"Generated {name} is stale or hand-edited; run uv run python scripts/generate_api.py")
            else:
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(source, target)
        print("Generated API is current." if check else "Generated models, server, FastAPI adapter, and client.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    generate(parser.parse_args().check)
