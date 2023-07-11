from server_browser_backend.ban_list import BanList
import os

def test_load_ban_list():
    key = "foo"
    ban_list = BanList(key, "test/resources/test_load_ban_list.txt")

    assert len(ban_list.get()) == 1
    assert ban_list.get().pop() == "127.0.0.1"

def test_update_ban_list():
    os.remove("test/resources/test_update_ban_list.txt")
    key = "foo"
    ban_list = BanList(key, "test/resources/test_update_ban_list.txt")
    assert len(ban_list.get()) == 0

    result = ban_list.add(key, "127.0.0.1")

    assert result, "Failed to update ban list with key"

    with open("test/resources/test_update_ban_list.txt", 'r') as f:
        lines = f.readlines()
        assert len(lines) == 1
        assert lines[0].strip() == "127.0.0.1"


    