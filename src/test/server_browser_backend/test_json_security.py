"""Reject JSON values that cannot be handled safely after decoding."""

import json

import pytest
from fastapi.testclient import TestClient


def test_deep_invalid_body_does_not_log_credentials(app, caplog):
    nested: object = "leaf"
    for _ in range(300):
        nested = [nested]
    body = {"token": {"secret": "credential-sentinel", "nested": nested}}
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/auth/login",
            content=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400
    assert "credential-sentinel" not in caplog.text
    assert "Unhandled exception" not in caplog.text


@pytest.mark.parametrize(
    "body",
    [
        {"token": {"secret": "credential-sentinel", "value": "\ud800"}},
        {"token": {"\udc00": "credential-sentinel"}},
    ],
)
def test_unpaired_surrogates_do_not_break_error_responses_or_log_credentials(
    app, caplog, body
):
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/auth/login",
            content=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400
    assert "credential-sentinel" not in caplog.text
    assert "Unhandled exception" not in caplog.text


@pytest.mark.parametrize("depth,expected", [(64, 410), (65, 400)])
def test_json_depth_boundary(app, depth, expected):
    nested: object = "leaf"
    for _ in range(depth - 1):
        nested = [nested]
    body = {"token": "sentinel", "extra": nested}
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            content=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == expected
