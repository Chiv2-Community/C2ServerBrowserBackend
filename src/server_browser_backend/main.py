from __future__ import annotations

from logging.config import dictConfig

from pygelf import GelfTcpHandler
from os import environ
import logging

from fastapi import FastAPI, Request, Response
from starlette.types import ASGIApp, Scope, Receive, Send
from server_browser_api.runtime import automatic_options, contract, DictKeyError, DictTypeError, JsonMissing, SchemaValidationError
from server_browser_backend.routes import api_v1
from server_browser_backend.routes.shared import Banned
from server_browser_backend.server_list import InvalidSecretKey, SecretKeyMissing

from server_browser_backend import routes
logger = logging.getLogger()

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s: %(message)s",
            }
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["stderr"]},
    }
)

graylog_host = environ.get("GRAYLOG_HOST", None)
graylog_port = int(environ.get("GRAYLOG_PORT", 12201))

if graylog_host is not None:
    logger.info(f"Logging to Graylog at {graylog_host}:{graylog_port} with level INFO")
    graylog_handler = GelfTcpHandler(host=graylog_host, port=graylog_port, include_extra_fields=True)
    graylog_handler.setLevel(logging.INFO)
    logger.addHandler(graylog_handler)


class ForwardedHeaders:
    """Preserve the existing one-trusted-proxy deployment contract.

    The backend must only be reachable through a proxy that overwrites forwarded
    headers. Trust the last value, as the old ProxyFix(x_for=1) did.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            if scope["method"] == "OPTIONS":
                response = automatic_options(scope["path"])
                if response is not None:
                    await response(scope, receive, send)
                    return
            scope = dict(scope)
            headers = dict(scope["headers"])
            forwarded = headers.get(b"x-forwarded-for")
            if forwarded:
                scope["client"] = (forwarded.decode("latin-1").split(",")[-1].strip(), 0)
            scheme = headers.get(b"x-forwarded-proto")
            if scheme:
                scope["scheme"] = scheme.decode("latin-1").split(",")[-1].strip()
        await self.app(scope, receive, send)


class ContractFastAPI(FastAPI):
    def openapi(self) -> dict:
        return contract()


app = ContractFastAPI(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)
app.add_middleware(ForwardedHeaders)


async def handle_api_exception(request: Request, error: Exception) -> Response:
    if isinstance(error, JsonMissing):
        return api_v1.handle_json_missing(request, error)
    if isinstance(error, DictKeyError):
        return api_v1.handle_dict_key_error(request, error)
    if isinstance(error, DictTypeError):
        return api_v1.handle_dict_type_error(request, error)
    if isinstance(error, SchemaValidationError):
        return api_v1.handle_schema_validation(request, error)
    if isinstance(error, SecretKeyMissing):
        return api_v1.handle_secret_key_missing(request, error)
    if isinstance(error, InvalidSecretKey):
        return api_v1.handle_invalid_secret_key(request, error)
    if isinstance(error, Banned):
        return api_v1.handle_banned_user(request, error)
    return api_v1.handle_general_exception(request, error)


for error_type in (JsonMissing, DictKeyError, DictTypeError, SchemaValidationError, SecretKeyMissing, InvalidSecretKey, Banned, Exception):
    app.add_exception_handler(error_type, handle_api_exception)

app.include_router(routes.compat_router)
app.include_router(routes.api_v1_router)
