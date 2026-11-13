"""Shared contract lookup remains independent of clients and HTTP adapters."""

import pytest

from server_browser_models import runtime


def test_operation_lookup_combines_path_and_operation_parameters(monkeypatch):
    inherited = {"name": "server_id", "in": "path"}
    local = {"name": "key", "in": "header"}
    declaration = {"operationId": "example", "parameters": [local], "responses": {}}
    monkeypatch.setattr(runtime, "contract", lambda: {
        "paths": {"/servers/{server_id}": {
            "parameters": [inherited], "summary": "Server endpoint", "post": declaration,
        }},
    })
    runtime.operation.cache_clear()
    try:
        result = runtime.operation("example")
        assert result == ("POST", "/servers/{server_id}", declaration, [inherited, local])
        assert runtime.operation("example") is result
    finally:
        runtime.operation.cache_clear()


def test_unknown_operation_reports_the_requested_identifier():
    with pytest.raises(ValueError, match="Unknown operation nonexistent"):
        runtime.operation("nonexistent")
