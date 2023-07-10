from server_browser_backend.server_list import _SecuredResource, ServerList


def test_secured_resource_correct_key():
    test_resource = _SecuredResource("foo", 10)
    updated = test_resource.update("foo", lambda x: x * 2)

    assert updated is not None
    assert updated.resource == 20


def test_secured_resource_invalid_key():
    test_resource = _SecuredResource("foo", 10)
    updated = test_resource.update("bar", lambda x: x * 2)

    assert updated is None
