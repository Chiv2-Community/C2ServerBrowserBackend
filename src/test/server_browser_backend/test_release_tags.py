import os
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "release-tags.sh"


def run_release_tags(tag, output):
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            **os.environ,
            "GITHUB_REF_NAME": tag,
            "GITHUB_REPOSITORY": "Chiv2-Community/C2ServerBrowserBackend",
            "GITHUB_OUTPUT": str(output),
        },
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("metadata", ["", "+abc123", "+build.123-sha"])
def test_release_tags(metadata, tmp_path):
    output = tmp_path / "output"
    version = f"1.1.0{metadata}"
    result = run_release_tags(f"v{version}", output)
    assert result.returncode == 0, result.stderr
    lines = output.read_text().splitlines()
    image = "ghcr.io/chiv2-community/c2serverbrowserbackend"
    assert f"version={version}" in lines
    assert f"image={image}" in lines
    assert f"{image}:{version.replace('+', '_')}" in lines
    assert (f"{image}:latest" in lines) == (metadata == "")


@pytest.mark.parametrize(
    "tag",
    [
        "v1.1",
        "v01.1.0",
        "v1.1.0+",
        "v1.1.0+a..b",
        "v1.1.0+bad_sha",
        "v1.1.0-rc.1",
        "v1.1.0+" + "a" * 128,
    ],
)
def test_invalid_release_tags(tag, tmp_path):
    output = tmp_path / "output"
    assert run_release_tags(tag, output).returncode != 0
    assert not output.exists()
