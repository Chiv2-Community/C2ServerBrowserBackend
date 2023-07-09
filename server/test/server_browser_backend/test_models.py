from server_browser_backend.models import SecuredResource, Server, Heartbeat, UpdateRegisteredServer


def test_secured_resource_correct_key():
    test_resource = SecuredResource("foo", 10)
    updated = test_resource.update("foo", lambda x: x * 2)

    assert updated is not None
    assert updated.get() == 20

def test_secured_resource_invalid_key():
    test_resource = SecuredResource("foo", 10)
    updated = test_resource.update("bar", lambda x: x * 2)

    assert updated is None


def test_is_same_server_true_validation():
    test_server_1 = Server("x", "y", 1, 0, "foo", "bar", "baz", 0, 0, [])
    test_server_2 = Server("x", "y", 1, 0, "foo", "bar", "baz", 0, 0, [])

    test_heartbeat = Heartbeat("x", "y", 1)

    test_update = UpdateRegisteredServer("x", "y", 1, "foo", 0, 0)

    assert test_server_1.is_same_server(test_server_2)
    assert test_server_2.is_same_server(test_server_1)
    assert test_server_1.is_same_server(test_heartbeat)
    assert test_server_1.is_same_server(test_update)


def test_is_same_server_false_validation():
    test_server_1 = Server("x", "y", 1, 0, "foo", "bar", "baz", 0, 0, [])
    test_server_2 = Server("y", "y", 1, 0, "foo", "bar", "baz", 0, 0, [])

    test_heartbeat = Heartbeat("x", "z", 1)

    test_update = UpdateRegisteredServer("x", "y", 0, "foo", 0, 0)

    assert not test_server_1.is_same_server(test_server_2)
    assert not test_server_2.is_same_server(test_server_1)
    assert not test_server_1.is_same_server(test_heartbeat)
    assert not test_server_1.is_same_server(test_update)
