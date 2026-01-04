from ipaddress import ip_network
import os

from server_browser_backend.ip_list import IpList

def clean_up_file(file_name):
    if os.path.exists(file_name):
        os.remove(file_name)


def test_load_ip_list_file():
    key = "foo"
    ip_list = IpList(key, "src/test/resources/test_load_ip_list.txt")

    print(ip_list.get_all(key))

    assert len(ip_list.get_all(key)) == 1
    assert ip_list.contains("127.0.0.1")

def test_ip_list_contains_ip_range():
    key = "foo"
    ip_list = IpList(key, "src/test/resources/test_ip_list_contains_ip_range.txt")

    assert len(ip_list.get_all(key)) == 1
    assert ip_list.contains("42.0.69.82")


def test_update_ip_list_file():
    clean_up_file("src/test/resources/test_update_ip_list.txt")
    key = "foo"
    ip_list = IpList(key, "src/test/resources/test_update_ip_list.txt")
    assert len(ip_list.get_all(key)) == 0

    result = ip_list.add(key, "127.0.0.1")

    assert result, "Failed to update ip list with key"

    with open("src/test/resources/test_update_ip_list.txt", "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        assert ip_network(lines[0].strip()) == ip_network("127.0.0.1")


def test_add_all_to_ip_list():
    clean_up_file("src/test/resources/test_add_all_to_ip_list.txt")
    key = "foo"
    ip_list = IpList(key, "src/test/resources/test_add_all_to_ip_list.txt")
    assert len(ip_list.get_all(key)) == 0

    adds = ["127.0.0.1", "255.255.255.255"]

    result = ip_list.add_all(key, adds)

    assert result, "Failed to update ip list with key"
    assert len(ip_list.get_all(key)) == 2
    assert ip_list.get_all(key) == set(map(lambda x: ip_network(x), adds))
