import pytest

from server_browser_backend.models.tbio import Game


@pytest.mark.parametrize(
    "address, expected",
    [
        ("2001:db8::1", "[2001:db8::1]"),
        ("[2001:db8::1]", "[2001:db8::1]"),
        ("192.0.2.1", "192.0.2.1"),
        ("server.example", "server.example"),
        ("invalid", "invalid"),
        ("", ""),
    ],
)
def test_format_address(address, expected):
    assert Game.format_address(address) == expected
