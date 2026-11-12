"""Contract and compatibility checks for the generated API boundary."""
from __future__ import annotations

import ast
import inspect
import json
from importlib.resources import files
from pathlib import Path
from typing import get_args

import pytest
import yaml
from openapi_schema_validator import OAS30Validator
from openapi_spec_validator import validate

from server_browser_api import models
from server_browser_api.apis.api_v1_api_base import BaseApiV1Api as ApiV1Controller
from server_browser_api.apis.chiv2_compat_api_base import BaseChiv2CompatApi as Chiv2CompatController
from fastapi.routing import APIRoute
from pydantic import BaseModel
from server_browser_api.models import Mod, ServerListResponse, ServerRegistrationRequest, ServerResponseWithIP
from server_browser_api.runtime import DictKeyError, DictTypeError, WireModel, contract, to_wire
from server_browser_backend.main import app
from server_browser_backend.routes import shared
from server_browser_backend.routes.api_v1 import BrowserApi
from server_browser_backend.routes.chiv2_compat import CompatibilityApi

from . import prepare_test_state
from .client import ApiClient

ROOT = Path(__file__).resolve().parents[4]
REGISTRATION = {
    "name": "Contract server", "description": "", "current_map": "Test Map",
    "player_count": 2, "max_players": 32,
    "ports": {"game": 7777, "ping": 7778, "a2s": 7779},
}


def assert_response_contract(path, method, response):
    operation = contract()["paths"][path][method.lower()]
    declaration = operation["responses"].get(str(response.status_code), operation["responses"].get("default"))
    assert declaration is not None
    media_type = response.content_type.split(";")[0]
    schema = declaration["content"][media_type]["schema"]
    if media_type == "application/json":
        OAS30Validator({"components": contract()["components"], **schema}).validate(response.get_json())


def test_spec_is_valid_and_generated_resources_match_source():
    source = yaml.safe_load((ROOT / "assets/chiv2-server-browser-api.yaml").read_text())
    validate(source)
    assert contract() == source
    assert yaml.safe_load(files("server_browser_api").joinpath("openapi.yaml").read_text()) == source


def test_runtime_routes_match_oas_exactly():
    def flatten(routes):
        for route in routes:
            # FastAPI 0.162+ retains included routers instead of copying routes.
            included = getattr(route, "original_router", None)
            if included is not None:
                yield from flatten(included.routes)
            else:
                yield route
    runtime_routes = list(flatten(app.routes))
    expected = {
        (path, method.upper())
        for path, entry in contract()["paths"].items()
        for method in entry if method in {"get", "post", "put", "patch", "delete", "options", "head"}
    }
    actual = {
        (rule.path, method)
        for rule in runtime_routes if isinstance(rule, APIRoute)
        for method in rule.methods - {"HEAD", "OPTIONS"}
    }
    assert actual == expected
    for rule in runtime_routes:
        assert isinstance(rule, APIRoute)
        assert rule.endpoint.__module__.startswith("server_browser_api.apis.")


def test_application_has_no_handwritten_route_declarations():
    for source in (ROOT / "src/server_browser_backend").rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"route", "add_url_rule"}, source
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        assert decorator.func.attr not in {"get", "post", "put", "patch", "delete"}, source


def test_generated_models_cover_every_schema():
    for name, schema in contract()["components"]["schemas"].items():
        model = getattr(models, name)
        if "anyOf" in schema:
            assert {candidate.__name__ for candidate in get_args(model)} == {
                alternative["$ref"].rsplit("/", 1)[1] for alternative in schema["anyOf"]
            }
            continue
        assert issubclass(model, WireModel)
        assert issubclass(model, BaseModel)
        assert model.__module__.startswith("server_browser_api.models.")
        if "properties" in schema:
            assert {field.alias or name for name, field in model.model_fields.items()} == set(schema["properties"])


def test_handlers_implement_generated_interfaces():
    assert isinstance(BrowserApi(), ApiV1Controller)
    assert isinstance(CompatibilityApi(), Chiv2CompatController)
    for interface in (ApiV1Controller, Chiv2CompatController):
        with pytest.raises(TypeError):
            interface()
        for name in interface.__abstractmethods__:
            signature = inspect.signature(getattr(interface, name))
            assert signature.return_annotation is not inspect.Signature.empty
            for parameter in list(signature.parameters.values())[1:]:
                assert parameter.annotation is not inspect.Signature.empty


def test_generated_defaults_and_nested_decoding():
    registration = ServerRegistrationRequest.from_json(REGISTRATION)
    assert registration.mods == []
    assert registration.password_protected is False
    assert registration.local_ip_address is None
    model = Mod.from_json({"name": "mod", "organization": "org", "version": "1"})
    assert model.active is False
    assert Mod.from_json({"name": "mod", "organization": "org", "version": "1", "active": False}) == model


@pytest.mark.parametrize("field,value", [("name", 1), ("player_count", "2"), ("mods", [1]), ("ports", [])])
def test_generated_decoding_rejects_wrong_types(field, value):
    with pytest.raises(DictTypeError):
        ServerRegistrationRequest.from_json({**REGISTRATION, field: value})


def test_required_fields_are_not_silently_defaulted():
    with pytest.raises(DictKeyError):
        ServerRegistrationRequest.from_json({key: value for key, value in REGISTRATION.items() if key != "name"})


def test_nullable_diagnostic_address_round_trips():
    prepare_test_state()
    with ApiClient() as client:
        registration = client.post("/api/v1/servers", json=REGISTRATION)
        value = {**registration.get_json()["server"], "ip_address": "127.0.0.1", "local_ip_address": None}
        assert to_wire(ServerResponseWithIP.from_json(value)) == value
        listing = ServerListResponse.from_json({"servers": [value]})
        assert isinstance(listing.servers[0], ServerResponseWithIP)
        assert to_wire(listing) == {"servers": [value]}


def test_all_successful_api_flows_match_response_schemas():
    prepare_test_state()
    with ApiClient() as client:
        response = client.post("/api/v1/servers", json=REGISTRATION)
        assert response.status_code == 201
        assert_response_contract("/api/v1/servers", "post", response)
        registration = response.get_json()
        server_id = registration["server"]["unique_id"]
        headers = {shared.KEY_HEADER: registration["key"]}
        admin_headers = {shared.ADMIN_KEY_HEADER: shared.ADMIN_KEY}
        requests = [
            ("/api/v1/servers", "/api/v1/servers", "GET", {}),
            ("/api/v1/auth/jwks.json", "/api/v1/auth/jwks.json", "GET", {}),
            ("/api/v1/check-banned/{ip}", "/api/v1/check-banned/192.0.2.1", "GET", {}),
            ("/api/tbio/GetCurrentGames", "/api/tbio/GetCurrentGames", "POST", {}),
            ("/api/tbio/GetMotd", "/api/tbio/GetMotd", "POST", {"json": {}}),
            ("/api/playfab/Client/Matchmake", "/api/playfab/Client/Matchmake", "POST", {"json": {"LobbyId": server_id}}),
            ("/api/v1/servers/{server_id}", f"/api/v1/servers/{server_id}", "PUT", {"headers": headers, "json": {"current_map": "Next", "player_count": 2, "max_players": 32}}),
            ("/api/v1/servers/{server_id}/heartbeat", f"/api/v1/servers/{server_id}/heartbeat", "POST", {"headers": headers}),
        ]
        for name, field in (("ban-list", "banned_ips"), ("verified-list", "verified_ips")):
            path = f"/api/v1/admin/{name}"
            requests += [(path, path, method, {"headers": admin_headers, **({"json": {field: ["192.0.2.1"]}} if method != "GET" else {})}) for method in ("PUT", "GET", "DELETE")]
        requests += [("/api/v1/servers/{server_id}", f"/api/v1/servers/{server_id}", "DELETE", {"headers": headers})]
        for template, path, method, kwargs in requests:
            response = client.open(path, method=method, **kwargs)
            assert response.status_code == 200, (path, response.get_data(as_text=True))
            assert_response_contract(template, method, response)


@pytest.mark.parametrize("value", [None, [], "body", 1, True])
def test_invalid_json_body_returns_400_without_mutation(value):
    prepare_test_state()
    with ApiClient() as client:
        response = client.post("/api/v1/servers", data=json.dumps(value), content_type="application/json")
        assert response.status_code == 400
        assert shared.server_list.get_all() == []
        assert_response_contract("/api/v1/servers", "post", response)


@pytest.mark.parametrize("path,body", [
    ("/api/tbio/GetMotd", {"Language": 1}),
    ("/api/playfab/Client/Matchmake", {}),
])
def test_compat_validation_errors_are_json_400(path, body):
    prepare_test_state()
    with ApiClient() as client:
        response = client.post(path, json=body)
        assert response.status_code == 400
        assert response.get_json()["status"] == "invalid_json_body"


@pytest.mark.parametrize("list_name,field", [("ban-list", "banned_ips"), ("verified-list", "verified_ips")])
def test_legacy_invalid_removal_response_is_preserved(list_name, field):
    prepare_test_state()
    with ApiClient() as client:
        response = client.delete(f"/api/v1/admin/{list_name}", headers={shared.ADMIN_KEY_HEADER: shared.ADMIN_KEY}, json={field: ["invalid"]})
        assert response.status_code == 403
        assert response.get_json()["message"] == "Invalid admin key"


def test_banned_request_policy_runs_before_body_decoding():
    prepare_test_state(ban_list=["127.0.0.1"])
    with ApiClient() as client:
        response = client.post("/api/v1/servers", json={})
        assert response.status_code == 403
        assert response.get_json()["message"] == "You are banned"
