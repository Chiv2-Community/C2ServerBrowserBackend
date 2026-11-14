"""Keep Rust CI checks identical across entry points and fail fast."""

import runpy
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("package", [False, True])
def test_rust_check_commands(package, monkeypatch, tmp_path):
    calls = []
    copies = []

    def capture(command, *, cwd, check):
        assert cwd == ROOT
        assert check is True
        calls.append(command)
        if command[1] == "package":
            output = Path(command[-1]) / "package"
            output.mkdir()
            (output / "example.crate").write_bytes(b"verified archive")
            (output / "ignored.txt").write_text("not an archive")

    monkeypatch.setattr(subprocess, "run", capture)
    monkeypatch.setattr(shutil, "copyfile", lambda source, target: copies.append((source.name, target)))
    monkeypatch.chdir(tmp_path)
    runner = runpy.run_path(str(ROOT / "scripts/check_rust.py"))
    runner["main"](["--package"] if package else [])
    manifest = ["--manifest-path", "sdk/rust/Cargo.toml"]
    expected = [
        ["cargo", "fmt", *manifest, "--all", "--", "--check"],
        ["cargo", "clippy", *manifest, "--locked", "--workspace", "--all-targets", "--all-features"],
        ["cargo", "clippy", *manifest, "--locked", "--workspace", "--all-targets",
         "--no-default-features", "--features",
         "server-browser-client/rustls-tls,server-browser-client-sdk/rustls-tls"],
        ["cargo", "doc", *manifest, "--locked", "--workspace", "--all-features", "--no-deps"],
        ["cargo", "test", *manifest, "--locked", "--workspace"],
        ["cargo", "test", *manifest, "--locked", "--workspace", "--release", "--all-features"],
    ]
    if package:
        expected.append(["cargo", "package", *manifest, "--locked", "--workspace",
                         "--allow-dirty", "--target-dir", calls[-1][-1]])
        assert not Path(calls[-1][-1]).exists()
        assert copies == [("example.crate", ROOT / "sdk/rust/target/package/example.crate")]
    else:
        assert not copies
    assert calls == expected


def test_rust_checks_stop_at_first_failure(monkeypatch):
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(subprocess, "run", fail)
    runner = runpy.run_path(str(ROOT / "scripts/check_rust.py"))
    with pytest.raises(subprocess.CalledProcessError):
        runner["main"](["--package"])
    assert len(calls) == 1
    assert calls[0][1] == "fmt"


def test_failed_package_verification_does_not_copy_archives(monkeypatch):
    package_targets = []

    def fail_package(command, **kwargs):
        if command[1] == "package":
            package_targets.append(Path(command[-1]))
            raise subprocess.CalledProcessError(1, command)

    def unexpected_copy(source, target):
        pytest.fail("unverified archive was copied")

    monkeypatch.setattr(subprocess, "run", fail_package)
    monkeypatch.setattr(shutil, "copyfile", unexpected_copy)
    runner = runpy.run_path(str(ROOT / "scripts/check_rust.py"))
    with pytest.raises(subprocess.CalledProcessError):
        runner["main"](["--package"])
    assert len(package_targets) == 1
    assert not package_targets[0].exists()
