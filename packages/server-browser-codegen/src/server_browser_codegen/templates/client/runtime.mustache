"""Generated HTTPX client support. DO NOT EDIT."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Generic, Mapping, TypeVar
from urllib.parse import quote

import httpx
from server_browser_models import models
from server_browser_models.runtime import DictKeyError, DictTypeError, operation, to_wire

T = TypeVar("T")
CT = TypeVar("CT", bound="ClientTransport")
AT = TypeVar("AT", bound="AsyncClientTransport")


class Unset:
    """An omitted parameter or body, distinct from explicit JSON null."""


UNSET = Unset()


@dataclass(frozen=True)
class ClientResponse(Generic[T]):
    body: T | None
    response: httpx.Response

    @property
    def status(self) -> int:
        return self.response.status_code

    @property
    def headers(self) -> httpx.Headers:
        return self.response.headers


class ClientDecodeError(ValueError):
    def __init__(self, response: httpx.Response):
        super().__init__(f"Invalid declared response: HTTP {response.status_code}")
        self.response = response


def request_arguments(operation_id: str, parameters: Mapping[str, Any], body: Any, *, base_url: str = "", default_headers: httpx.Headers | None = None) -> dict[str, Any]:
    method, path, _, definitions = operation(operation_id)
    headers: dict[str, str] = {}
    query: dict[str, Any] = {}
    cookies: dict[str, Any] = {}
    for parameter in definitions:
        value = parameters.get(parameter["name"], UNSET)
        if isinstance(value, Unset):
            continue
        if value is None:
            raise ValueError(f"Null is not supported for HTTP parameter {parameter['name']}")
        if parameter["in"] == "path":
            path = path.replace("{" + parameter["name"] + "}", quote(str(value), safe=""))
        elif parameter["in"] == "header":
            headers[parameter["name"]] = str(value)
        elif parameter["in"] == "query":
            query[parameter["name"]] = to_wire(value)
        elif parameter["in"] == "cookie":
            cookies[parameter["name"]] = value
    arguments: dict[str, Any] = {"method": method, "url": base_url + path, "headers": headers, "params": query}
    if cookies:
        arguments["cookies"] = cookies
    if not isinstance(body, Unset):
        # exclude_unset preserves omitted optional model fields without dropping explicit null.
        value = body.model_dump(mode="json", by_alias=True, exclude_unset=True) if hasattr(body, "model_dump") else to_wire(body)
        arguments["content"] = json.dumps(value).encode()
        headers["Content-Type"] = "application/json"
    if default_headers is not None:
        merged_headers = default_headers.copy()
        merged_headers.update(headers)
        arguments["headers"] = merged_headers
    return arguments


def decode_response(operation_id: str, response: httpx.Response) -> ClientResponse[Any]:
    declaration = operation(operation_id)[2]["responses"]
    expected = declaration.get(str(response.status_code), declaration.get("default"))
    if expected is None:
        return ClientResponse(None, response)
    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    content = expected.get("content", {}).get(media_type)
    if content is None:
        return ClientResponse(None, response)
    if media_type != "application/json":
        return ClientResponse(response.text, response)
    try:
        value = response.json()
        schema = content["schema"]
        if "$ref" in schema:
            model = getattr(models, schema["$ref"].rsplit("/", 1)[1])
            value = model.from_json(value)
        return ClientResponse(value, response)
    except (ValueError, TypeError, KeyError, AttributeError, DictKeyError, DictTypeError) as error:
        raise ClientDecodeError(response) from error


class ClientTransport:
    def __init__(self, base_url: str, *, session: httpx.Client | None = None, timeout: float = 10.0, headers: Mapping[str, str] | None = None):
        self._owned = session is None
        self._session = session if session is not None else httpx.Client(timeout=timeout)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = httpx.Headers(headers or {})

    def _request(self, operation_id: str, *, parameters: Mapping[str, Any], body: Any = UNSET) -> ClientResponse[Any]:
        arguments = request_arguments(operation_id, parameters, body, base_url=self._base_url, default_headers=self._headers)
        # Custom credential headers must never follow redirects, including HTTP downgrades.
        return decode_response(operation_id, self._session.request(**arguments, timeout=self._timeout, follow_redirects=False))

    def close(self) -> None:
        if self._owned:
            self._session.close()

    def __enter__(self: CT) -> CT:
        return self

    def __exit__(self, *args):
        self.close()


class AsyncClientTransport:
    def __init__(self, base_url: str, *, session: httpx.AsyncClient | None = None, timeout: float = 10.0, headers: Mapping[str, str] | None = None):
        self._owned = session is None
        self._session = session if session is not None else httpx.AsyncClient(timeout=timeout)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = httpx.Headers(headers or {})

    async def _request(self, operation_id: str, *, parameters: Mapping[str, Any], body: Any = UNSET) -> ClientResponse[Any]:
        arguments = request_arguments(operation_id, parameters, body, base_url=self._base_url, default_headers=self._headers)
        # Keep injected sessions from forwarding credentials to a redirected target.
        return decode_response(operation_id, await self._session.request(**arguments, timeout=self._timeout, follow_redirects=False))

    async def aclose(self) -> None:
        if self._owned:
            await self._session.aclose()

    async def __aenter__(self: AT) -> AT:
        return self

    async def __aexit__(self, *args):
        await self.aclose()
