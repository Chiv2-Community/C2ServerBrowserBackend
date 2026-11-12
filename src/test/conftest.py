"""Keep API tests from writing the checkout's operator configuration."""
import pytest

from server_browser_backend.routes import shared


@pytest.fixture(autouse=True)
def isolated_ip_list_files(tmp_path, monkeypatch):
    monkeypatch.setattr(shared.ban_list, "ip_list_path", str(tmp_path / "ban_list.txt"))
    monkeypatch.setattr(shared.verified_list, "ip_list_path", str(tmp_path / "verified_list.txt"))
