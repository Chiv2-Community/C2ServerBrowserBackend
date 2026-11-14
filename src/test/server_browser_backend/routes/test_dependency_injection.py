"""Each application owns an explicit service graph, shared only within that graph."""
import json
import subprocess
import sys
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from server_browser_server.apis.api_v1_api_base import BaseApiV1Api
from server_browser_server.apis.chiv2_compat_api_base import BaseChiv2CompatApi
from server_browser_models.models import JwksResponse, StatusResponse
from server_browser_server.runtime import ApiResponse
from server_browser_backend.application import Application
from server_browser_backend.server_list import ServerList
from server_browser_backend.auth.signing import SigningKeys, provision

REGISTRATION = {
    "name": "injected server", "description": "", "current_map": "Test Map",
    "player_count": 0, "max_players": 32,
    "ports": {"game": 7777, "ping": 7778, "a2s": 7779},
}


def test_application_accepts_generated_interfaces_without_concrete_services():
    browser = Mock(spec=BaseApiV1Api)
    compatibility = Mock(spec=BaseChiv2CompatApi)
    browser.login.return_value = ApiResponse(StatusResponse(status="injected", message="injected policy"), 410)
    browser.send_swagger.return_value = ApiResponse("openapi: test", content_type="text/yaml", headers={"Cache-Control": "no-store"})
    compatibility.tbio_get_servers.return_value = ApiResponse(
        StatusResponse(status="forbidden", message="injected policy"), 403,
    )
    application = Application(browser, compatibility, debug_mode=False)
    with TestClient(application) as client:
        login = client.post("/api/v1/auth/login", json={"token": "input-token"})
        listing = client.post("/api/tbio/GetCurrentGames")
        specification = client.get("/api/v1/swagger.yaml")
    assert login.status_code == 410
    assert login.json()["status"] == "injected"
    assert listing.status_code == 403
    assert listing.json()["message"] == "injected policy"
    assert specification.text == "openapi: test"
    assert specification.headers["cache-control"] == "no-store"
    browser.login.assert_called_once()
    compatibility.tbio_get_servers.assert_called_once()


def test_api_implementations_share_the_injected_services(app):
    browser = app.browser_api
    compatibility = app.compatibility_api
    assert browser.server_list is compatibility.server_list
    assert browser.policy is compatibility.policy
    assert browser.policy.ban_list is browser.ban_list
    assert browser.policy.verified_list is browser.verified_list


def test_applications_isolate_registrations_policy_keys_and_visibility(app_factory, admin_key, tmp_path):
    provision(tmp_path / "first-signing.json")
    provision(tmp_path / "second-signing.json")
    first = app_factory(expose_ips=lambda: True, signing_keys=SigningKeys(tmp_path / "first-signing.json"))
    second = app_factory(expose_ips=lambda: False, signing_keys=SigningKeys(tmp_path / "second-signing.json"))
    assert first.browser_api.signing_keys.get_jwks_response() != second.browser_api.signing_keys.get_jwks_response()
    assert first.browser_api.ban_list.ip_list_path != second.browser_api.ban_list.ip_list_path
    assert first.browser_api.verified_list.ip_list_path != second.browser_api.verified_list.ip_list_path

    with TestClient(first, client=("127.0.0.1", 50000)) as one, TestClient(second, client=("127.0.0.1", 50000)) as two:
        assert one.post("/api/v1/servers", json=REGISTRATION).status_code == 201
        assert len(one.post("/api/tbio/GetCurrentGames").json()["Data"]["Games"]) == 1
        assert two.get("/api/v1/servers").json() == {"servers": []}
        assert two.post("/api/tbio/GetCurrentGames").json()["Data"]["Games"] == []
        assert two.post("/api/v1/servers", json=REGISTRATION).status_code == 201
        assert "ip_address" in one.get("/api/v1/servers").json()["servers"][0]
        assert "ip_address" not in two.get("/api/v1/servers").json()["servers"][0]

        first.browser_api.ban_list.add_all(admin_key, ["127.0.0.1"])
        first.browser_api.verified_list.add_all(admin_key, ["192.0.2.1"])
        assert one.get("/api/v1/servers").status_code == 403
        assert two.get("/api/v1/servers").status_code == 200
        assert not second.browser_api.ban_list.contains("127.0.0.1")
        assert not second.browser_api.verified_list.contains("192.0.2.1")


def test_jwks_uses_the_constructed_signing_service(app_factory):
    first_tokens = Mock(spec=SigningKeys)
    second_tokens = Mock(spec=SigningKeys)
    first_tokens.get_jwks_response.return_value = JwksResponse(keys=[])
    second_tokens.get_jwks_response.return_value = JwksResponse(keys=[])
    first = app_factory(signing_keys=first_tokens)
    second = app_factory(signing_keys=second_tokens)
    with TestClient(first, client=("192.0.2.1", 50000)) as one, TestClient(second, client=("192.0.2.2", 50000)) as two:
        first_login = one.get("/api/v1/auth/jwks.json")
        second_login = two.get("/api/v1/auth/jwks.json")
    assert first_login.status_code == second_login.status_code == 200
    assert first_login.json() == second_login.json() == {"keys": []}
    first_tokens.get_jwks_response.assert_called_once_with()
    second_tokens.get_jwks_response.assert_called_once_with()


def test_error_configuration_is_scoped_to_the_application(app_factory):
    class FailingRegistry(ServerList):
        def get_all(self):
            raise RuntimeError("injected failure")

    debug = app_factory(server_list=FailingRegistry(), debug_mode=True)
    production = app_factory(server_list=FailingRegistry(), debug_mode=False)
    with TestClient(debug, raise_server_exceptions=False) as one, TestClient(production, raise_server_exceptions=False) as two:
        detailed = one.get("/api/v1/servers")
        redacted = two.get("/api/v1/servers")
    assert detailed.status_code == redacted.status_code == 500
    assert detailed.json()["message"] == "injected failure"
    assert "RuntimeError: injected failure" in detailed.json()["stack"]
    assert redacted.json() == {"status": "error", "message": "An unexpected error occurred.", "context": None}


def test_motd_uses_the_injected_directory_and_policy(app_factory, tmp_path, admin_key):
    (tmp_path / "en.json").write_text(json.dumps({"Motd": "injected default"}))
    (tmp_path / "en_banned.json").write_text(json.dumps({"Motd": "injected banned"}))
    application = app_factory(motd_directory=tmp_path)
    with TestClient(application, client=("127.0.0.1", 50000)) as client:
        assert client.post("/api/tbio/GetMotd", json={"Language": "zz"}).json()["Data"]["Motd"] == "injected default"
        application.browser_api.ban_list.add_all(admin_key, ["127.0.0.1"])
        assert client.post("/api/tbio/GetMotd", json={}).json()["Data"]["Motd"] == "injected banned"


def test_component_imports_do_not_construct_production_services():
    code = '''
import sys
from unittest.mock import patch
with patch("cryptography.hazmat.primitives.asymmetric.rsa.generate_private_key", side_effect=AssertionError("unexpected key generation")):
    with patch("server_browser_backend.ip_list.IpList.__init__", side_effect=AssertionError("unexpected config access")):
        import server_browser_backend.application
        import server_browser_backend.routes.api_v1
        import server_browser_backend.routes.chiv2_compat
assert "server_browser_backend.main" not in sys.modules
'''
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


@pytest.mark.parametrize("modules, forbidden", [
    (
        ("server_browser_backend.routes.api_v1", "server_browser_backend.routes.chiv2_compat"),
        ("fastapi", "starlette", "server_browser_fastapi"),
    ),
    (
        ("server_browser_backend.application",),
        ("server_browser_backend.routes.api_v1", "server_browser_backend.routes.chiv2_compat"),
    ),
])
def test_imports_respect_application_transport_boundary(modules, forbidden):
    code = f'''
import importlib
import importlib.abc
import sys

class RejectImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".") for name in {forbidden!r}):
            raise AssertionError("Unexpected dependency: " + fullname)

sys.meta_path.insert(0, RejectImports())
for module in {modules!r}:
    importlib.import_module(module)
assert "server_browser_backend.main" not in sys.modules
'''
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)
