from server_browser_backend.secured_resource import SecuredResource


def test_secured_resource_correct_key():
    test_resource = SecuredResource("foo", 10)
    updated = test_resource.with_resource("foo", test_resource.resource * 2)

    assert updated is not None
    assert updated.resource == 20


def test_secured_resource_invalid_key():
    test_resource = SecuredResource("foo", 10)
    updated = test_resource.with_resource("bar", test_resource.resource * 2)

    assert updated is None
