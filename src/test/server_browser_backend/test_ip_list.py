import os

from server_browser_backend.ip_list import IpList


def clean_up_file(file_name):
    if os.path.exists(file_name):
        os.remove(file_name)


def test_load_ip_list_file():
    key = "foo"
    ip_list = IpList(key, "src/test/resources/test_load_ip_list.txt")

    assert len(ip_list.get_all()) == 1
    assert ip_list.get_all().pop() == "127.0.0.1"


def test_update_ip_list_file():
    clean_up_file("src/test/resources/test_update_ip_list.txt")
    key = "foo"
    ip_list = IpList(key, "src/test/resources/test_update_ip_list.txt")
    assert len(ip_list.get_all()) == 0

    result = ip_list.add(key, "127.0.0.1")

    assert result, "Failed to update ip list with key"

    with open("src/test/resources/test_update_ip_list.txt", "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        assert lines[0].strip() == "127.0.0.1"


def test_add_all_to_ip_list():
    clean_up_file("src/test/resources/test_add_all_to_ip_list.txt")
    key = "foo"
    ip_list = IpList(key, "src/test/resources/test_add_all_to_ip_list.txt")
    assert len(ip_list.get_all()) == 0

    adds = ["127.0.0.1", "255.255.255.255"]

    result = ip_list.add_all(key, adds)

    assert result, "Failed to update ip list with key"
    assert len(ip_list.get_all()) == 2
    assert ip_list.get_all() == set(adds)
