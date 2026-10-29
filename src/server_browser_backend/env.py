import os


def show_registered_ips() -> bool:
    return _get_env_bool("EXPOSE_REGISTERED_IPS")


def _get_env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "y")
