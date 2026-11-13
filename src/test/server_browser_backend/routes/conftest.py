"""Native ASGI clients with explicit peer addresses."""
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient

from server_browser_backend.main import app

from . import prepare_test_state


@pytest.fixture
def client_for_ip():
    prepare_test_state()
    with ExitStack() as clients:
        def create(address: str) -> TestClient:
            return clients.enter_context(TestClient(
                app, client=(address, 50000), raise_server_exceptions=False,
            ))
        yield create


@pytest.fixture
def client(client_for_ip):
    return client_for_ip("127.0.0.1")
