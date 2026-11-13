"""Construct isolated application graphs without production configuration."""
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from server_browser_backend.application import Application
from server_browser_backend.env import show_registered_ips
from server_browser_backend.ip_list import IpList
from server_browser_backend.routes.api_v1 import BrowserApi
from server_browser_backend.routes.chiv2_compat import CompatibilityApi
from server_browser_backend.routes.shared import RequestPolicy
from server_browser_backend.server_list import ServerList
from server_browser_backend.token_reissuer import TokenReissuer


@pytest.fixture
def admin_key():
    return "test-admin-key"


@pytest.fixture
def app_factory(tmp_path, admin_key):
    count = 0

    def create(*, token_reissuer=None, server_list=None, debug_mode=True, expose_ips=show_registered_ips, motd_directory=None):
        nonlocal count
        directory = tmp_path / str(count)
        directory.mkdir()
        count += 1
        if server_list is None:
            server_list = ServerList(heartbeat_timeout=65)
        ban_list = IpList(admin_key, str(directory / "ban_list.txt"))
        verified_list = IpList(admin_key, str(directory / "verified_list.txt"))
        verified_list.add_all(admin_key, ["127.0.0.1"])
        policy = RequestPolicy(ban_list, verified_list)
        if token_reissuer is None:
            token_reissuer = TokenReissuer(
                private_key=rsa.generate_private_key(public_exponent=65537, key_size=2048),
                kid="server-browser-backend-key-1", eos_jwks="https://example.invalid/jwks.json",
            )
        return Application(
            BrowserApi(
                server_list=server_list, ban_list=ban_list, verified_list=verified_list,
                policy=policy, token_reissuer=token_reissuer, show_registered_ips=expose_ips,
            ),
            CompatibilityApi(
                server_list=server_list, policy=policy,
                motd_directory=motd_directory or Path(__file__).resolve().parents[2] / "assets/motd",
            ),
            debug_mode=debug_mode,
        )
    return create


@pytest.fixture
def app(app_factory):
    return app_factory()


@pytest.fixture
def browser(app):
    return app.browser_api
