import pytest

from server_browser_backend.env import show_registered_ips


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        ("", False),
        ("0", False),
        ("false", False),
        ("1", True),
        ("true", True),
        ("yes", True),
        ("y", True),
        ("  TRUE \n", True),
    ],
)
def test_show_registered_ips(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("EXPOSE_REGISTERED_IPS", raising=False)
    else:
        monkeypatch.setenv("EXPOSE_REGISTERED_IPS", value)
    assert show_registered_ips() is expected


def test_show_registered_ips_reads_current_environment(monkeypatch):
    monkeypatch.setenv("EXPOSE_REGISTERED_IPS", "0")
    assert show_registered_ips() is False
    monkeypatch.setenv("EXPOSE_REGISTERED_IPS", "1")
    assert show_registered_ips() is True
