import os

from server_browser_backend.ban_list import BanList


def clean_up_file(file_name):
    if os.path.exists(file_name):
        os.remove(file_name)


def test_load_ban_list_file():
    key = "foo"
    ban_list = BanList(key, "test/resources/test_load_ban_list.txt")

    assert len(ban_list.get_all()) == 1
    assert ban_list.get_all().pop() == "127.0.0.1"


def test_update_ban_list_file():
    clean_up_file("test/resources/test_update_ban_list.txt")
    key = "foo"
    ban_list = BanList(key, "test/resources/test_update_ban_list.txt")
    assert len(ban_list.get_all()) == 0

    result = ban_list.add(key, "127.0.0.1")

    assert result, "Failed to update ban list with key"

    with open("test/resources/test_update_ban_list.txt", "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        assert lines[0].strip() == "127.0.0.1"


def test_add_all_to_ban_list():
    clean_up_file("test/resources/test_add_all_to_ban_list.txt")
    key = "foo"
    ban_list = BanList(key, "test/resources/test_add_all_to_ban_list.txt")
    assert len(ban_list.get_all()) == 0

    adds = ["127.0.0.1", "255.255.255.255"]

    result = ban_list.add_all(key, adds)

    assert result, "Failed to update ban list with key"
    assert len(ban_list.get_all()) == 2
    assert ban_list.get_all() == set(adds)
