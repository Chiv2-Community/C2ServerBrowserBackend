from ipaddress import IPv4Address, IPv6Address, ip_address

import pytest

from server_browser_backend.dict_util import TYPE_DECODERS, DictKeyError, DictTypeError, get_or, get_or_optional
from server_browser_backend.ip_address import IPAddress


@pytest.mark.parametrize("getter", [get_or, get_or_optional])
@pytest.mark.parametrize(
    "expected_type, value",
    [
        (IPAddress, "192.0.2.1"),
        (IPAddress, "2001:db8::1"),
        (IPAddress, "2001:0db8:0:0:0:0:0:1"),
    ],
)
def test_get_ip_address(getter, expected_type, value):
    parsed = getter({"ip": value}, "ip", expected_type)
    assert (parsed.value if isinstance(parsed, IPAddress) else parsed) == ip_address(value)
    assert isinstance(parsed, expected_type)
    assert getter({"ip": parsed}, "ip", expected_type) is parsed


@pytest.mark.parametrize("getter", [get_or, get_or_optional])
@pytest.mark.parametrize(
    "expected_type, value",
    [
        (IPAddress, "invalid"),
        (IPAddress, 123),
        (IPAddress, None),
        (IPAddress, True),
        (IPAddress, []),
    ],
)
def test_get_invalid_ip_address(getter, expected_type, value):
    data = {"ip": value}
    with pytest.raises(DictTypeError) as error:
        getter(data, "ip", expected_type)
    assert error.value.key == "ip"
    assert error.value.value == value
    assert error.value.context == data
    assert error.value.expected_type == expected_type


def test_get_missing_ip_address():
    assert get_or_optional({}, "ip", IPAddress) is None
    default = IPAddress(IPv4Address("192.0.2.1"))
    assert get_or({}, "ip", IPAddress, lambda: default) is default
    with pytest.raises(DictKeyError):
        get_or({}, "ip", IPAddress)


def test_get_does_not_coerce_other_types():
    assert get_or({"value": "123"}, "value", str) == "123"
    with pytest.raises(DictTypeError):
        get_or({"value": "123"}, "value", int)


@pytest.mark.parametrize("getter", [get_or, get_or_optional])
@pytest.mark.parametrize(
    "expected_type, value",
    [(str, "text"), (int, 123), (float, 1.5), (bool, False), (list, [1]), (dict, {"a": 1})],
)
def test_get_json_types(getter, expected_type, value):
    assert expected_type in TYPE_DECODERS
    assert TYPE_DECODERS[expected_type](value) is value
    assert getter({"value": value}, "value", expected_type) is value


@pytest.mark.parametrize("getter", [get_or, get_or_optional])
@pytest.mark.parametrize(
    "expected_type, value",
    [(str, 123), (int, "123"), (float, "1.5"), (bool, "false"), (list, "abc"), (dict, [])],
)
def test_get_json_types_rejects_coercion(getter, expected_type, value):
    with pytest.raises(DictTypeError):
        getter({"value": value}, "value", expected_type)


def test_concrete_ip_decoders_removed():
    assert IPv4Address not in TYPE_DECODERS
    assert IPv6Address not in TYPE_DECODERS


@pytest.mark.parametrize("getter", [get_or, get_or_optional])
def test_get_uses_registered_decoder(getter, monkeypatch):
    monkeypatch.setitem(TYPE_DECODERS, float, float)
    assert getter({"value": "1.5"}, "value", float) == 1.5
    with pytest.raises(DictTypeError):
        getter({"value": "invalid"}, "value", float)


def test_get_checks_decoded_type(monkeypatch):
    monkeypatch.setitem(TYPE_DECODERS, float, lambda value: value)
    with pytest.raises(DictTypeError):
        get_or({"value": "1.5"}, "value", float)
