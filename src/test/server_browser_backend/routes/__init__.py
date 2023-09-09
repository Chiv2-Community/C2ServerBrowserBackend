from server_browser_backend.routes import shared

LOCALHOST = "127.0.0.1"

def prepare_test_state(allow_list=[LOCALHOST], ban_list=[]):
    shared.server_list.clear()

    shared.allow_list.clear(shared.ADMIN_KEY)
    shared.allow_list.add_all(shared.ADMIN_KEY, allow_list)

    shared.ban_list.clear(shared.ADMIN_KEY)
    shared.ban_list.add_all(shared.ADMIN_KEY, ban_list)
