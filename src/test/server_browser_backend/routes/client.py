"""HTTP-only adapter retaining the existing Flask-era regression assertions.

All requests go through the real ASGI application via Starlette's TestClient;
this adapter only translates test-client method and response accessor names.
"""
from typing import Any

import httpx
from fastapi.testclient import TestClient

from server_browser_backend.main import app


class TestResponse:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.status_code = response.status_code
        self.headers = response.headers
        self.content_type = response.headers.get("content-type", "")
        self.data = response.content

    def get_json(self) -> Any:
        return self.response.json()

    def get_data(self, as_text: bool = False) -> str | bytes:
        return self.response.text if as_text else self.response.content


class ApiClient:
    def __init__(self):
        self.client = TestClient(app, client=("127.0.0.1", 50000), raise_server_exceptions=False)

    def __enter__(self):
        self.client.__enter__()
        return self

    def __exit__(self, *args):
        return self.client.__exit__(*args)

    def open(self, path: str, method: str = "GET", **kwargs: Any) -> TestResponse:
        overrides = kwargs.pop("environ_overrides", {})
        if "content_type" in kwargs:
            kwargs.setdefault("headers", {})["Content-Type"] = kwargs.pop("content_type")
        if "data" in kwargs and isinstance(kwargs["data"], (str, bytes)):
            kwargs["content"] = kwargs.pop("data")
        if overrides:
            assert set(overrides) == {"REMOTE_ADDR"}
            with TestClient(app, client=(overrides["REMOTE_ADDR"], 50000), raise_server_exceptions=False) as client:
                return TestResponse(client.request(method, path, **kwargs))
        return TestResponse(self.client.request(method, path, **kwargs))

    def get(self, path: str, **kwargs: Any) -> TestResponse:
        return self.open(path, "GET", **kwargs)

    def post(self, path: str, **kwargs: Any) -> TestResponse:
        return self.open(path, "POST", **kwargs)

    def put(self, path: str, **kwargs: Any) -> TestResponse:
        return self.open(path, "PUT", **kwargs)

    def delete(self, path: str, **kwargs: Any) -> TestResponse:
        return self.open(path, "DELETE", **kwargs)
