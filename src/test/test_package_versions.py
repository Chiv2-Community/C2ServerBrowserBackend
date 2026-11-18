"""Check coordinated metadata and exercise the configured standard bump tool."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    return tomllib.loads(path.read_text())


def manifests(root):
    return [root / "pyproject.toml", root / "mock/pyproject.toml",
            *sorted(root.glob("sdk/python/*/pyproject.toml"))]


def check_versions(root):
    version = load(root / ".bumpversion.toml")["tool"]["bumpversion"]["current_version"]
    projects = [load(path) for path in manifests(root)]
    names = {project["project"]["name"] for project in projects}
    for project in projects:
        assert project["project"]["version"] == version
        dependencies = project["project"].get("dependencies", [])
        for group in project.get("dependency-groups", {}).values():
            dependencies = [*dependencies, *group]
        for dependency in dependencies:
            requirement = Requirement(dependency)
            if requirement.name in names:
                assert requirement.specifier == SpecifierSet(f"=={version}")
    workspace = load(root / "sdk/rust/Cargo.toml")["workspace"]
    assert workspace["package"]["version"] == version
    for dependency in workspace["dependencies"].values():
        assert dependency["version"] == f"={version}"
    for crate in root.glob("sdk/rust/*/Cargo.toml"):
        assert load(crate)["package"]["version"] == {"workspace": True}
    return version


def test_package_versions_match():
    check_versions(ROOT)


@pytest.mark.parametrize("version", ["1.3.0-alpha.4", "1.3.0-beta.1", "1.3.0-rc.1", "1.3.0"])
def test_bump_updates_manifests_and_internal_pins(tmp_path, version):
    for source in [ROOT / ".bumpversion.toml", *manifests(ROOT),
                   ROOT / "sdk/rust/Cargo.toml", *ROOT.glob("sdk/rust/*/Cargo.toml")]:
        destination = tmp_path / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    tool = shutil.which("bump-my-version")
    assert tool is not None
    subprocess.run([tool, "bump", "--new-version", version], cwd=tmp_path, check=True)
    assert check_versions(tmp_path) == version
