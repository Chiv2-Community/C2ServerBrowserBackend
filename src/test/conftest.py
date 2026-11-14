"""Construct isolated application graphs without production configuration."""

from pathlib import Path

import pytest

from server_browser_backend.application import Application
from server_browser_backend.env import show_registered_ips
from server_browser_backend.ip_list import IpList
from server_browser_backend.routes.api_v1 import BrowserApi
from server_browser_backend.routes.chiv2_compat import CompatibilityApi
from server_browser_backend.routes.shared import RequestPolicy
from server_browser_backend.server_list import ServerList


@pytest.fixture
def admin_key():
    return "test-admin-key"


@pytest.fixture
def app_factory(tmp_path, admin_key):
    count = 0

    def create(
        *,
        signing_keys=None,
        server_list=None,
        debug_mode=True,
        expose_ips=show_registered_ips,
        motd_directory=None,
        trusted_proxies=("127.0.0.1/32", "::1/128"),
    ):
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
        return Application(
            BrowserApi(
                server_list=server_list,
                ban_list=ban_list,
                verified_list=verified_list,
                policy=policy,
                signing_keys=signing_keys,
                show_registered_ips=expose_ips,
            ),
            CompatibilityApi(
                server_list=server_list,
                policy=policy,
                motd_directory=motd_directory
                or Path(__file__).resolve().parents[2] / "assets/motd",
            ),
            debug_mode=debug_mode,
            trusted_proxies=trusted_proxies,
        )

    return create


@pytest.fixture
def app(app_factory):
    return app_factory()


@pytest.fixture
def browser(app):
    return app.browser_api
