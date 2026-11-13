from ipaddress import ip_address

import pytest

from server_browser_models.runtime import legacy_ip_address


@pytest.mark.parametrize(
    "address, expected",
    [
        ("2001:db8::1", "[2001:db8::1]"),
        ("2001:0db8:0:0:0:0:0:1", "[2001:db8::1]"),
        ("192.0.2.1", "192.0.2.1"),
    ],
)
def test_format_address(address, expected):
    assert legacy_ip_address(ip_address(address)) == expected
