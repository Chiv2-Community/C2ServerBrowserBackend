"""Assemble an ASGI application from explicitly constructed API services."""
from functools import partial

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

from server_browser_api.apis.api_v1_api import create_router as browser_router
from server_browser_api.apis.chiv2_compat_api import create_router as compatibility_router
from server_browser_api.runtime import (
    DictKeyError, DictTypeError, JsonMissing, SchemaValidationError, automatic_options, contract,
)
from server_browser_backend.routes import api_v1
from server_browser_backend.routes.api_v1 import BrowserApi
from server_browser_backend.routes.chiv2_compat import CompatibilityApi
from server_browser_backend.routes.shared import Banned
from server_browser_backend.server_list import InvalidSecretKey, SecretKeyMissing


class ForwardedHeaders:
    """Trust the last forwarded value from one trusted, header-overwriting proxy."""
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


class Application(FastAPI):
    def __init__(self, browser_api: BrowserApi, compatibility_api: CompatibilityApi, *, debug_mode: bool):
        super().__init__(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)
        self.browser_api = browser_api
        self.compatibility_api = compatibility_api
        self.add_middleware(ForwardedHeaders)
        self.exception_handler(JsonMissing)(api_v1.handle_json_missing)
        self.exception_handler(DictKeyError)(api_v1.handle_dict_key_error)
        self.exception_handler(DictTypeError)(api_v1.handle_dict_type_error)
        self.exception_handler(SchemaValidationError)(api_v1.handle_schema_validation)
        self.exception_handler(SecretKeyMissing)(api_v1.handle_secret_key_missing)
        self.exception_handler(InvalidSecretKey)(api_v1.handle_invalid_secret_key)
        self.exception_handler(Banned)(api_v1.handle_banned_user)
        self.exception_handler(Exception)(partial(api_v1.handle_general_exception, debug_mode=debug_mode))
        self.include_router(compatibility_router(compatibility_api))
        self.include_router(browser_router(browser_api))

    def openapi(self) -> dict:
        return contract()
