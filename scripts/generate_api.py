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
TARGET = ROOT / "packages/server-browser-api/src/server_browser_api"


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


def same_sources(left: Path, right: Path) -> bool:
    if not right.is_dir():
        return False
    left_files = {p.relative_to(left) for p in left.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    right_files = {p.relative_to(right) for p in right.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    return left_files == right_files and all(filecmp.cmp(left / p, right / p, shallow=False) for p in left_files)


def generate(check: bool) -> None:
    spec = yaml.safe_load((ROOT / "assets/chiv2-server-browser-api.yaml").read_text())
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
        generated = output / "src/server_browser_api"
        # Keep the contract/bindings, not the generator's example application.
        for source in list(generated.rglob("*")):
            if source.is_file() and not (
                source.relative_to(generated).parts[0] in ("models", "apis")
                or source.relative_to(generated).as_posix() in ("__init__.py", "runtime.py", "py.typed")
            ):
                source.unlink()
        for example in ("models/extra_models.py",):
            (generated / example).unlink(missing_ok=True)
        (generated / "contract.json").write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
        (generated / "openapi.yaml").write_text((ROOT / "assets/chiv2-server-browser-api.yaml").read_text())
        for source in generated.rglob("*.py"):
            ast.parse(source.read_text(), filename=str(source))
        if check:
            if not same_sources(generated, TARGET):
                raise SystemExit("Generated API is stale or hand-edited; run uv run python scripts/generate_api.py")
            print("Generated API is current.")
        else:
            if TARGET.exists():
                shutil.rmtree(TARGET)
            shutil.copytree(generated, TARGET)
            print("Generated server-browser-api package.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    generate(parser.parse_args().check)
