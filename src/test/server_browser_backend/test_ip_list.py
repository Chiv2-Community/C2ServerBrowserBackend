from ipaddress import ip_network

import pytest

from server_browser_backend.ip_list import IpList


@pytest.mark.parametrize("network, address", [
    ("127.0.0.1", "127.0.0.1"),
    ("42.0.69.0/24", "42.0.69.82"),
    ("2001:db8::/64", "2001:db8::1"),
])
def test_load_ip_list_file(tmp_path, network, address):
    path = tmp_path / "ips.txt"
    path.write_text(f"  {network}  \n")
    ip_list = IpList("key", str(path))

    assert ip_list.get_all("key") == {ip_network(network)}
    assert ip_list.contains(address)


def test_update_ip_list_file(tmp_path):
    path = tmp_path / "ips.txt"
    ip_list = IpList("key", str(path))
    assert ip_list.get_all("key") == set()

    assert ip_list.add("key", "127.0.0.1") is True
    assert path.read_text() == "127.0.0.1/32"


@pytest.mark.parametrize("remove", [False, True])
def test_change_ip_list_persists_all_entries(tmp_path, remove):
    path = tmp_path / "ips.txt"
    ip_list = IpList("key", str(path))
    assert ip_list.add_all("key", ["192.0.2.1"]) is True
    entries = ["127.0.0.1", "2001:db8::1"]
    if remove:
        assert ip_list.add_all("key", entries) is True

    change = ip_list.remove_all if remove else ip_list.add_all
    assert change("key", iter(entries)) is True

    expected = {ip_network("192.0.2.1")}
    if not remove:
        expected.update(ip_network(ip) for ip in entries)
    assert ip_list.get_all("key") == expected
    assert IpList("key", str(path)).get_all("key") == expected


@pytest.mark.parametrize("remove", [False, True])
def test_invalid_entry_does_not_partially_change_ip_list(tmp_path, remove):
    path = tmp_path / "ips.txt"
    ip_list = IpList("key", str(path))
    assert ip_list.add("key", "192.0.2.1") is True
    before = path.read_bytes()

    change = ip_list.remove_all if remove else ip_list.add_all
    valid_entry = "192.0.2.1" if remove else "2001:db8::1"
    assert change("key", iter([valid_entry, "invalid"])) is None

    assert ip_list.get_all("key") == {ip_network("192.0.2.1")}
    assert path.read_bytes() == before


@pytest.mark.parametrize("remove", [False, True])
def test_invalid_key_does_not_consume_entries_or_write(tmp_path, remove):
    path = tmp_path / "ips.txt"
    ip_list = IpList("key", str(path))

    def entries():
        raise AssertionError("unauthorized input must not be consumed")
        yield "127.0.0.1"

    change = ip_list.remove_all if remove else ip_list.add_all
    assert change("wrong-key", entries()) is None
    assert ip_list.get_all("key") == set()
    assert not path.exists()
