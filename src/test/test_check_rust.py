"""Keep Rust CI checks identical across entry points and fail fast."""

import runpy
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("package", [False, True])
def test_rust_check_commands(package, monkeypatch, tmp_path):
    calls = []

    def capture(command, *, cwd, check):
        assert cwd == ROOT
        assert check is True
        calls.append(command)

    monkeypatch.setattr(subprocess, "run", capture)
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
        expected.append(["cargo", "package", *manifest, "--locked", "--workspace", "--allow-dirty"])
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
