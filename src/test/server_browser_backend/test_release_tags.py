import os
from pathlib import Path
import subprocess

import pytest
import yaml


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "release-tags.sh"


def run_release_tags(tag, output, workflow_ref=None):
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            **os.environ,
            "GITHUB_REF_NAME": workflow_ref or tag,
            "RELEASE_TAG": tag,
            "GITHUB_REPOSITORY": "Chiv2-Community/C2ServerBrowserBackend",
            "GITHUB_OUTPUT": str(output),
        },
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("metadata", ["", "+abc123", "+build.123-sha"])
@pytest.mark.parametrize("prerelease", ["", "-alpha", "-alpha.1", "-rc.1", "-0", "-0a", "-alpha-1"])
def test_release_tags(metadata, prerelease, tmp_path):
    output = tmp_path / "output"
    version = f"1.3.0{prerelease}{metadata}"
    result = run_release_tags(f"v{version}", output)
    assert result.returncode == 0, result.stderr
    lines = output.read_text().splitlines()
    image = "ghcr.io/chiv2-community/c2serverbrowserbackend"
    assert f"version={version}" in lines
    assert f"image={image}" in lines
    assert f"{image}:{version.replace('+', '_')}" in lines
    assert (f"{image}:latest" in lines) == (metadata == "" and prerelease == "")


@pytest.mark.parametrize(
    "tag",
    [
        "v1.1",
        "v01.1.0",
        "v1.1.0+",
        "v1.1.0+a..b",
        "v1.1.0+bad_sha",
        "v1.1.0-",
        "v1.1.0-01",
        "v1.1.0-alpha.01",
        "v1.1.0-alpha..1",
        "v1.1.0-alpha_1",
        "v1.1.0-alpha\ninjected",
        "v1.1.0+" + "a" * 128,
    ],
)
def test_invalid_release_tags(tag, tmp_path):
    output = tmp_path / "output"
    assert run_release_tags(tag, output).returncode != 0
    assert not output.exists()


def test_dispatch_tag_is_independent_of_workflow_branch(tmp_path):
    output = tmp_path / "output"
    result = run_release_tags("v1.3.0-alpha", output, workflow_ref="main")
    assert result.returncode == 0, result.stderr
    assert "version=1.3.0-alpha" in output.read_text().splitlines()


def test_workflow_uses_a_nonreserved_environment_variable_for_tag():
    workflow = yaml.load((SCRIPT.parents[1] / ".github/workflows/publish.yml").read_text(), Loader=yaml.BaseLoader)
    step = next(step for step in workflow["jobs"]["publish"]["steps"] if step.get("id") == "version")
    assert step["env"] == {"RELEASE_TAG": "${{ inputs.tag || github.ref_name }}"}
    assert "refs/tags/${RELEASE_TAG}^{commit}" in step["run"]
