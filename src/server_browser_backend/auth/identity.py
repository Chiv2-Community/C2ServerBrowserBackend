"""Canonical verified Discord identity, separate from game/platform IDs."""


def validate_discord_id(value: str) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 20
        or not value.isascii()
        or not value.isdecimal()
        or value.startswith("0")
        or int(value) >= 2**64
    ):
        raise ValueError("Invalid Discord identity")
