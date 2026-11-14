"""Policy revocation and persistence must not leave stale grants or lose bans."""

import os
import stat
from concurrent.futures import ThreadPoolExecutor
from ipaddress import ip_network
from threading import Event

import pytest
from fastapi.testclient import TestClient

from server_browser_backend.ip_list import IpList

REGISTRATION = {
    "name": "policy-test",
    "description": "",
    "current_map": "map",
    "player_count": 0,
    "max_players": 32,
    "ports": {"game": 7777, "ping": 7778, "a2s": 7779},
}


@pytest.mark.parametrize("expose_ips", [False, True])
def test_verified_revocation_and_grant_apply_to_live_registrations(
    app_factory, admin_key, expose_ips
):
    app = app_factory(expose_ips=lambda: expose_ips)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        registration = client.post("/api/v1/servers", json=REGISTRATION).json()
        server_id = registration["server"]["unique_id"]
        assert registration["server"]["is_verified"] is True
        admin_headers = {"X-CHIV2-SERVER-BROWSER-ADMIN-KEY": admin_key}
        for method, expected in (("DELETE", False), ("PUT", True)):
            changed = client.request(
                method,
                "/api/v1/admin/verified-list",
                json={"verified_ips": ["127.0.0.1"]},
                headers=admin_headers,
            )
            assert changed.status_code == 200
            listing = client.get("/api/v1/servers").json()["servers"][0]
            assert listing["is_verified"] is expected
            game = client.post("/api/tbio/GetCurrentGames").json()["Data"]["Games"][0]
            assert game["Official"] is expected
            assert game["Tags"]["OFFICIAL_b"] == str(expected).lower()
            heartbeat = client.post(
                f"/api/v1/servers/{server_id}/heartbeat",
                headers={"X-CHIV2-SERVER-BROWSER-KEY": registration["key"]},
            )
            assert heartbeat.status_code == 200
            assert heartbeat.json()["server"]["is_verified"] is expected


def test_revocation_during_registration_cannot_leave_a_stale_verified_grant(
    app, browser, admin_key, monkeypatch
):
    register = browser.server_list.register

    def revoke_then_register(server):
        assert server.is_verified is True
        assert browser.verified_list.remove(admin_key, "127.0.0.1")
        return register(server)

    monkeypatch.setattr(browser.server_list, "register", revoke_then_register)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.post("/api/v1/servers", json=REGISTRATION).status_code == 201
        assert (
            client.get("/api/v1/servers").json()["servers"][0]["is_verified"] is False
        )
        assert (
            client.post("/api/tbio/GetCurrentGames").json()["Data"]["Games"][0][
                "Official"
            ]
            is False
        )


def test_verified_status_uses_observed_server_ip_not_viewer_or_local_address(app):
    with TestClient(app, client=("192.0.2.1", 1234)) as client:
        response = client.post(
            "/api/v1/servers", json={**REGISTRATION, "local_ip_address": "127.0.0.1"}
        )
        assert response.json()["server"]["is_verified"] is False
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert (
            client.get("/api/v1/servers").json()["servers"][0]["is_verified"] is False
        )
        assert (
            client.post("/api/tbio/GetCurrentGames").json()["Data"]["Games"][0][
                "Official"
            ]
            is False
        )


@pytest.mark.parametrize("operation", ["add", "remove", "clear"])
@pytest.mark.parametrize("failure", ["replace", "fsync"])
def test_failed_policy_write_preserves_memory_and_disk(
    tmp_path, monkeypatch, operation, failure
):
    path = tmp_path / "ips.txt"
    listing = IpList("key", str(path))
    listing.add("key", "192.0.2.1")
    before = path.read_bytes()

    def fail_write(*args):
        raise OSError("write failed")

    monkeypatch.setattr(os, failure, fail_write)
    with pytest.raises(OSError, match="write failed"):
        if operation == "clear":
            listing.clear("key")
        else:
            getattr(listing, operation)(
                "key", "192.0.2.2" if operation == "add" else "192.0.2.1"
            )
    assert listing.get_all("key") == {ip_network("192.0.2.1")}
    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".ips.txt-*"))


def test_readers_do_not_observe_a_policy_before_it_is_persisted(tmp_path, monkeypatch):
    listing = IpList("key", str(tmp_path / "ips.txt"))
    listing.add("key", "192.0.2.1")
    fsync = os.fsync
    flushing = Event()
    release = Event()

    def pause_fsync(descriptor):
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            flushing.set()
            assert release.wait(timeout=10)
        return fsync(descriptor)

    monkeypatch.setattr(os, "fsync", pause_fsync)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(listing.add, "key", "192.0.2.2")
        try:
            assert flushing.wait(timeout=10)
            assert not listing.contains("192.0.2.2")
            assert listing.get_all("key") == {ip_network("192.0.2.1")}
        finally:
            release.set()
        assert future.result(timeout=10)
    assert listing.contains("192.0.2.2")


def test_concurrent_policy_updates_preserve_all_bans(tmp_path):
    path = tmp_path / "ips.txt"
    listing = IpList("key", str(path))
    addresses = [f"192.0.2.{index}" for index in range(1, 33)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert all(executor.map(lambda address: listing.add("key", address), addresses))
    expected = {ip_network(address) for address in addresses}
    assert listing.get_all("key") == expected
    assert IpList("key", str(path)).get_all("key") == expected


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink behavior")
def test_policy_write_does_not_follow_a_predictable_temp_symlink(tmp_path):
    path = tmp_path / "ips.txt"
    target = tmp_path / "unrelated.txt"
    target.write_text("untouched")
    path.with_suffix(".txt.tmp").symlink_to(target)
    listing = IpList("key", str(path))
    assert listing.add("key", "192.0.2.1")
    assert target.read_text() == "untouched"
    assert not path.is_symlink()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_policy_read_returns_a_detached_snapshot(tmp_path):
    listing = IpList("key", str(tmp_path / "ips.txt"))
    listing.add("key", "192.0.2.1")
    snapshot = listing.get_all("key")
    snapshot.clear()
    assert listing.contains("192.0.2.1")


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory fsync")
def test_post_replace_flush_failure_keeps_memory_and_disk_consistent(
    tmp_path, monkeypatch
):
    path = tmp_path / "ips.txt"
    listing = IpList("key", str(path))
    listing.add("key", "192.0.2.1")
    fsync = os.fsync

    def fail_directory_flush(descriptor):
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError("directory flush failed")
        return fsync(descriptor)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail_directory_flush)
        with pytest.raises(OSError, match="directory flush failed"):
            listing.remove("key", "192.0.2.1")
    assert listing.get_all("key") == set()
    assert IpList("key", str(path)).get_all("key") == set()
