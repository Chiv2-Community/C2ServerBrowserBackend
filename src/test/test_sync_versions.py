"""Coordinate Python and Rust package versions without build-time checkout dependencies."""

import os
import runpy
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = runpy.run_path(str(ROOT / "scripts/sync_versions.py"))


@pytest.mark.parametrize(
    "version,expected",
    [
        ("1.3.0", "1.3.0"),
        ("1.3.0-alpha.3", "1.3.0a3"),
        ("1.3.0-beta.10", "1.3.0b10"),
        ("1.3.0-rc.0", "1.3.0rc0"),
    ],
)
def test_python_version(version, expected):
    assert RUNNER["python_version"](version) == expected


@pytest.mark.parametrize(
    "version",
    ["v1.3.0", "1.3", "01.3.0", "1.3.0-alpha", "1.3.0-alpha-2",
     "1.3.0-alpha.03", "1.3.0-dev.1", "1.3.0+abc", "1.3.0\nignored"],
)
def test_unsupported_version_is_rejected(version):
    with pytest.raises(ValueError):
        RUNNER["python_version"](version)


@pytest.fixture
def repository(tmp_path):
    for path in [ROOT / "VERSION", ROOT / "pyproject.toml", ROOT / "mock/pyproject.toml",
                 *ROOT.glob("sdk/python/*/pyproject.toml"), ROOT / "sdk/rust/Cargo.toml",
                 *ROOT.glob("sdk/rust/*/Cargo.toml")]:
        destination = tmp_path / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
    return tmp_path


def test_sync_updates_all_manifests_and_internal_constraints(repository):
    (repository / "VERSION").write_text("2.0.0-beta.10\n")
    changed = RUNNER["synchronize"](repository)
    assert len(changed) == 8
    for path in repository.rglob("pyproject.toml"):
        text = path.read_text()
        assert 'version = "2.0.0b10"' in text
        assert "==1.3.0a3" not in text
    assert 'version = "=2.0.0-beta.10"' in (repository / "sdk/rust/Cargo.toml").read_text()
    assert '"httpx>=0.28,<1"' in (repository / "pyproject.toml").read_text()
    assert RUNNER["synchronize"](repository, check=True, tag="v2.0.0-beta.10") == []
    assert RUNNER["synchronize"](repository) == []


def test_drift_check_does_not_write(repository):
    (repository / "VERSION").write_text("2.0.0\n")
    before = {path: path.read_bytes() for path in repository.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="Version drift"):
        RUNNER["synchronize"](repository, check=True)
    assert before == {path: path.read_bytes() for path in before}


def test_cargo_crates_cannot_override_the_workspace_version(repository):
    manifest = repository / "sdk/rust/server-browser-client-sdk/Cargo.toml"
    manifest.write_text(manifest.read_text().replace("version.workspace = true", 'version = "0.0.0"'))
    with pytest.raises(ValueError, match="Version drift"):
        RUNNER["synchronize"](repository, check=True)
    assert RUNNER["synchronize"](repository) == [manifest]
    assert "version.workspace = true" in manifest.read_text()


@pytest.mark.parametrize("tag", ["v1.3.0", "v1.3.0-alpha.2", "v1.3.0-alpha.3+abc", "1.3.0-alpha.3"])
def test_tag_mismatch_is_rejected_before_writing(repository, tag):
    with pytest.raises(ValueError, match="Release tag must be"):
        RUNNER["synchronize"](repository, tag=tag)


def test_current_manifests_match_shared_version():
    version = (ROOT / "VERSION").read_text().strip()
    assert RUNNER["synchronize"](ROOT, check=True, tag=f"v{version}") == []


def test_sync_refreshes_lockfiles_and_check_is_read_only(monkeypatch):
    calls = []
    monkeypatch.setattr(RUNNER["main"].__globals__["subprocess"], "run",
                        lambda command, **kwargs: calls.append((command, kwargs["cwd"])))
    RUNNER["main"](["--check"])
    assert calls == []
    RUNNER["main"]([])
    assert calls == [
        (["uv", "lock"], ROOT),
        (["uv", "lock"], ROOT / "mock"),
        (["cargo", "update", "--workspace"], ROOT / "sdk/rust"),
    ]


@pytest.mark.parametrize("version,latest", [("1.3.0-alpha.3", False), ("1.3.0", True)])
def test_shell_publisher_uses_shared_semver_without_publishing(version, latest, tmp_path):
    (tmp_path / "VERSION").write_text(version + "\n")
    (tmp_path / "ci.sh").write_text("exit 0\n")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for name in ("uv", "docker", "git"):
        command = binaries / name
        command.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "$COMMAND_LOG"\n')
        command.chmod(0o755)
    log = tmp_path / "commands"
    subprocess.run(
        ["bash", str(ROOT / "publish.sh")], cwd=tmp_path, check=True,
        env={**os.environ, "PATH": f"{binaries}{os.pathsep}{os.environ['PATH']}",
             "COMMAND_LOG": str(log)},
    )
    commands = log.read_text()
    assert f"scripts/sync_versions.py --check --tag v{version}" in commands
    assert f"backend:{version}" in commands
    assert ("backend:latest" in commands) == latest
    assert f"git tag v{version}" in commands
    assert f"git push origin refs/tags/v{version}" in commands
    assert "--tags" not in commands
