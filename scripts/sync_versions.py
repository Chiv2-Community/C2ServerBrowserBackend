"""Synchronize package manifests and lockfiles from the repository VERSION."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(alpha|beta|rc)\.(0|[1-9][0-9]*))?"
)


def python_version(version: str) -> str:
    """Use the common SemVer/PEP 440 subset, without lossy build metadata."""
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError("Expected X.Y.Z or X.Y.Z-{alpha,beta,rc}.N")
    major, minor, patch, stage, number = match.groups()
    suffix = {"alpha": "a", "beta": "b", "rc": "rc"}
    return f"{major}.{minor}.{patch}" + (
        f"{suffix[stage]}{number}" if stage else ""
    )


def replace_version(text: str, section: str, version: str | None) -> str:
    pattern = re.compile(
        rf"(^\[{re.escape(section)}\]\n)(.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL
    )

    def replace(match: re.Match[str]) -> str:
        body, count = re.subn(
            r'^version(?:\.workspace)? = (?:"[^"]+"|true|false)$',
            f'version = "{version}"' if version is not None else "version.workspace = true",
            match[2], flags=re.MULTILINE,
        )
        if count != 1:
            raise ValueError(f"Expected one version in [{section}]")
        return match[1] + body

    result, count = pattern.subn(replace, text)
    if count != 1:
        raise ValueError(f"Expected one [{section}] section")
    return result


def synchronize(root: Path, check: bool = False, tag: str | None = None) -> list[Path]:
    version = (root / "VERSION").read_text().strip()
    python = python_version(version)
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"Release tag must be v{version}, not {tag}")
    manifests = [
        root / "pyproject.toml",
        root / "mock/pyproject.toml",
        *sorted(root.glob("sdk/python/*/pyproject.toml")),
    ]
    names = []
    for path in manifests:
        name = re.search(r'^name = "([^"]+)"$', path.read_text(), re.MULTILINE)
        if name is None:
            raise ValueError(f"Missing package name: {path}")
        names.append(name[1])
    dependencies = re.compile(
        r'("(?:' + "|".join(re.escape(name) for name in names) + r')==)[^"]+'
    )
    updates = {
        path: dependencies.sub(
            lambda match: match[1] + python,
            replace_version(path.read_text(), "project", python),
        )
        for path in manifests
    }
    cargo = root / "sdk/rust/Cargo.toml"
    updates[cargo] = re.sub(
        r'(server-browser-[\w-]+ = \{ version = ")=[^"]+',
        lambda match: match[1] + "=" + version,
        replace_version(cargo.read_text(), "workspace.package", version),
    )
    for path in sorted(root.glob("sdk/rust/*/Cargo.toml")):
        updates[path] = replace_version(path.read_text(), "package", None)
    changed = [path for path, text in updates.items() if path.read_text() != text]
    if check and changed:
        raise ValueError(
            "Version drift; run python scripts/sync_versions.py:\n"
            + "\n".join(str(path.relative_to(root)) for path in changed)
        )
    for path in changed:
        path.write_text(updates[path])
    return changed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="reject drift without writing")
    parser.add_argument("--tag", help="also require this release tag to match VERSION")
    args = parser.parse_args(argv)
    try:
        synchronize(ROOT, check=args.check, tag=args.tag)
    except ValueError as error:
        parser.error(str(error))
    if not args.check:
        for directory in (ROOT, ROOT / "mock"):
            subprocess.run(["uv", "lock"], cwd=directory, check=True)
        subprocess.run(
            ["cargo", "update", "--workspace"], cwd=ROOT / "sdk/rust", check=True
        )


if __name__ == "__main__":
    main()
