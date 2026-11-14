"""Shared generator invocation and failure diagnostics."""

import subprocess
import sys

import pytest

from server_browser_codegen.generation import run_generator


@pytest.mark.parametrize("returncode", [0, 1])
def test_generator_process(tmp_path, monkeypatch, capsys, returncode):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, returncode, "generator output", "generator error")

    monkeypatch.setattr(subprocess, "run", run)
    if returncode:
        with pytest.raises(subprocess.CalledProcessError):
            run_generator(["-g", "rust"], tmp_path)
    else:
        run_generator(["-g", "rust"], tmp_path)

    assert calls == [(
        [sys.executable, "-c", "from openapi_generator_cli import cli; cli()", "generate", "-g", "rust"],
        {"cwd": tmp_path, "capture_output": True, "text": True},
    )]
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == ("generator output\ngenerator error\n" if returncode else "")
