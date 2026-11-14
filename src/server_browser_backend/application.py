"""Assemble an ASGI application from explicitly constructed API services."""
from functools import partial

from fastapi import FastAPI
from server_browser_fastapi.apis.api_v1_api import \
    create_router as browser_router
from server_browser_fastapi.apis.chiv2_compat_api import \
    create_router as compatibility_router
from server_browser_fastapi.runtime import JsonMissing, automatic_options
from server_browser_models.runtime import (DictKeyError, DictTypeError,
                                           SchemaValidationError, contract)
from server_browser_server.apis.api_v1_api_base import BaseApiV1Api
from server_browser_server.apis.chiv2_compat_api_base import BaseChiv2CompatApi
from starlette.types import ASGIApp, Receive, Scope, Send

from server_browser_backend import error_handlers
from server_browser_backend.request_logging import request_scope, requestor_ip
from server_browser_backend.routes.shared import Banned
from server_browser_backend.server_list import (InvalidSecretKey,
                                                SecretKeyMissing)


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
            # ASGI scopes are per request. Keep routing/proxy context visible to
            # the outer error handler and Uvicorn access logger as well.
            headers = dict(scope["headers"])
            forwarded = headers.get(b"x-forwarded-for")
            if forwarded:
                scope["client"] = (forwarded.decode("latin-1").split(",")[-1].strip(), 0)
            scheme = headers.get(b"x-forwarded-proto")
            if scheme:
                scope["scheme"] = scheme.decode("latin-1").split(",")[-1].strip()
        await self.app(scope, receive, send)


class Application(FastAPI):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Keep context around the outer error handler too; proxy middleware
        # updates this per-request scope before endpoints and access logging.
        token = request_scope.set(scope if scope["type"] == "http" else None)
        try:
            await super().__call__(scope, receive, send)
        except BaseException as exc:
            # Uvicorn logs escaping errors after the request context is reset.
            setattr(exc, "_request_log_ip", requestor_ip(request_scope.get()))
            raise
        finally:
            request_scope.reset(token)

    def __init__(self, browser_api: BaseApiV1Api, compatibility_api: BaseChiv2CompatApi, *, debug_mode: bool):
        super().__init__(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)
        self.browser_api = browser_api
        self.compatibility_api = compatibility_api
        self.add_middleware(ForwardedHeaders)
        self.exception_handler(JsonMissing)(error_handlers.handle_json_missing)
        self.exception_handler(DictKeyError)(error_handlers.handle_dict_key_error)
        self.exception_handler(DictTypeError)(error_handlers.handle_dict_type_error)
        self.exception_handler(SchemaValidationError)(error_handlers.handle_schema_validation)
        self.exception_handler(SecretKeyMissing)(error_handlers.handle_secret_key_missing)
        self.exception_handler(InvalidSecretKey)(error_handlers.handle_invalid_secret_key)
        self.exception_handler(Banned)(error_handlers.handle_banned_user)
        self.exception_handler(Exception)(partial(error_handlers.handle_general_exception, debug_mode=debug_mode))
        self.include_router(compatibility_router(compatibility_api))
        self.include_router(browser_router(browser_api))

    def openapi(self) -> dict:
        return contract()
