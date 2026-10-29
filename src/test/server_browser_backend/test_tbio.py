from ipaddress import ip_address

import pytest

from server_browser_backend.models.tbio import Game


@pytest.mark.parametrize(
    "address, expected",
    [
        ("2001:db8::1", "[2001:db8::1]"),
        ("2001:0db8:0:0:0:0:0:1", "[2001:db8::1]"),
        ("192.0.2.1", "192.0.2.1"),
    ],
)
def test_format_address(address, expected):
    assert Game.format_address(ip_address(address)) == expected
