"""Translate backend errors into HTTP responses at the FastAPI boundary."""

import logging
import traceback

from fastapi import Request, Response
from server_browser_fastapi.runtime import JsonMissing, render_response
from server_browser_models.models import ErrorResponse, StatusResponse
from server_browser_models.runtime import (
    DictKeyError,
    DictTypeError,
    SchemaValidationError,
)
from server_browser_server.runtime import ApiResponse

from server_browser_backend.routes.shared import KEY_HEADER, Banned, status
from server_browser_backend.server_list import InvalidSecretKey, SecretKeyMissing

logger = logging.getLogger(__name__)


def log_rejection(request: Request, reason: str) -> None:
    """Record request identity without logging headers, query strings, or bodies."""
    logger.warning(
        "Request rejected: %s operation=%s method=%s server_id=%r requester_ip=%r",
        reason,
        getattr(request.scope.get("route"), "name", "unknown"),
        request.method,
        request.path_params.get("server_id"),
        request.client.host if request.client else None,
    )


async def handle_json_missing(request: Request, error: JsonMissing) -> Response:
    log_rejection(request, "missing or malformed JSON body")
    return render_response(status("missing_json_body", "JSON body is required", 400))


async def handle_dict_key_error(request: Request, error: DictKeyError) -> Response:
    log_rejection(request, "missing required JSON field")
    return render_response(
        ApiResponse(
            StatusResponse(
                status="invalid_json_body",
                message=f"Missing key '{error.key}'",
                context=error.context,
            ),
            400,
        )
    )


async def handle_dict_type_error(request: Request, error: DictTypeError) -> Response:
    log_rejection(request, "invalid JSON field type")
    message = f"Invalid type for key '{error.key}'. Got '{error.actual_type.__name__}' with value '{error.value}', but expected '{error.expected_type.__name__}'"
    return render_response(
        ApiResponse(
            StatusResponse(
                status="invalid_json_body",
                message=message,
                context=error.context,
            ),
            400,
        )
    )


async def handle_secret_key_missing(
    request: Request, error: SecretKeyMissing
) -> Response:
    log_rejection(request, "missing secret key")
    return render_response(status("no_key", KEY_HEADER + " header not specified", 400))


async def handle_schema_validation(
    request: Request, error: SchemaValidationError
) -> Response:
    log_rejection(request, "request schema validation failed")
    return render_response(status("invalid_json_body", str(error), 400))


async def handle_invalid_secret_key(
    request: Request, error: InvalidSecretKey
) -> Response:
    log_rejection(request, "invalid secret key")
    return render_response(status("forbidden", "Invalid secret key", 403))


async def handle_banned_user(request: Request, error: Banned) -> Response:
    log_rejection(request, "banned requester")
    return render_response(status("forbidden", "You are banned", 403))


async def handle_general_exception(
    request: Request, error: Exception, *, debug_mode: bool
) -> Response:
    logger.error(
        "Unhandled exception operation=%s method=%s server_id=%r requester_ip=%r: %s",
        getattr(request.scope.get("route"), "name", "unknown"),
        request.method,
        request.path_params.get("server_id"),
        request.client.host if request.client else None,
        error,
        exc_info=True,
    )
    if debug_mode:
        return render_response(
            ApiResponse(
                ErrorResponse(
                    status="error",
                    message=str(error),
                    stack=traceback.format_exc(),
                ),
                500,
            )
        )
    return render_response(status("error", "An unexpected error occurred.", 500))
