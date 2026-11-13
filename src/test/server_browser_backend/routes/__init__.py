from typing import Iterable

from server_browser_backend.routes.api_v1 import BrowserApi

LOCALHOST = "127.0.0.1"

def prepare_test_state(browser: BrowserApi, admin_key: str, verified_list: Iterable[str] = (LOCALHOST,), ban_list: Iterable[str] = ()) -> None:
    browser.server_list.clear()

    browser.verified_list.clear(admin_key)
    browser.verified_list.add_all(admin_key, verified_list)

    browser.ban_list.clear(admin_key)
    browser.ban_list.add_all(admin_key, ban_list)
