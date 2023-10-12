from server_browser_backend.routes import shared

LOCALHOST = "127.0.0.1"

def prepare_test_state(verified_list=[LOCALHOST], ban_list=[]):
    shared.server_list.clear()

    shared.verified_list.clear(shared.ADMIN_KEY)
    shared.verified_list.add_all(shared.ADMIN_KEY, verified_list)

    shared.ban_list.clear(shared.ADMIN_KEY)
    shared.ban_list.add_all(shared.ADMIN_KEY, ban_list)
