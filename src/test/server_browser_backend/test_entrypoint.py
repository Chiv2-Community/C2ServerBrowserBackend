"""The container starts installed wheels without uv or a source workspace."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/entrypoint.sh"
ROOT = SCRIPT.parent.parent


@pytest.mark.parametrize("configured", [False, True])
def test_entrypoint_passes_environment_and_extra_arguments_to_uvicorn(
    tmp_path, configured
):
    executable = tmp_path / "uvicorn"
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    executable.chmod(0o755)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("UVICORN_")
    }
    environment["PATH"] = str(tmp_path) + os.pathsep + environment["PATH"]
    settings = (
        {
            "UVICORN_HOST": "::",
            "UVICORN_PORT": "9090",
            "UVICORN_WORKERS": "2",
            "UVICORN_LOG_LEVEL": "debug",
            "UVICORN_KEEP_ALIVE": "9",
        }
        if configured
        else {}
    )
    environment.update(settings)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--limit-concurrency", "7"],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.splitlines() == [
        "server_browser_backend.main:app",
        "--host",
        settings.get("UVICORN_HOST", "0.0.0.0"),
        "--port",
        settings.get("UVICORN_PORT", "8080"),
        "--workers",
        settings.get("UVICORN_WORKERS", "1"),
        "--log-level",
        settings.get("UVICORN_LOG_LEVEL", "info"),
        "--timeout-keep-alive",
        settings.get("UVICORN_KEEP_ALIVE", "5"),
        "--no-proxy-headers",
        "--limit-concurrency",
        "7",
    ]


@pytest.mark.parametrize("version", ["latest", "1.2.3"])
def test_docker_launcher_uses_published_image_and_entrypoint_defaults(
    tmp_path, version
):
    executable = tmp_path / "docker"
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    executable.chmod(0o755)
    result = subprocess.run(
        ["bash", str(ROOT / "run-in-docker.sh"), "-v", version, "-k", "test key"],
        cwd=tmp_path,
        env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == [
        "run",
        "-p",
        "8080:8080",
        "-e",
        "ADMIN_KEY=test key",
        "-e",
        "CONFIG_DIR=/config",
        "-v",
        f"{tmp_path}/config:/config",
        "-it",
        f"ghcr.io/chiv2-community/c2serverbrowserbackend:{version}",
    ]
    assert (tmp_path / "config").is_dir()
