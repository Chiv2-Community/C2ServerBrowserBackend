"""Generated FastAPI transport support. DO NOT EDIT."""
from functools import lru_cache
import json
import re
from typing import Any

from fastapi import Request, Response
from starlette.responses import JSONResponse
from openapi_schema_validator import OAS30Validator
from server_browser_models.runtime import (
    DictKeyError, DictTypeError, SchemaValidationError, contract, operation, parse_ip_address, to_wire,
)
from server_browser_server.runtime import ApiResponse


class JsonMissing(Exception):
    pass


class PayloadTooLarge(Exception):
    pass


def automatic_options(path: str) -> Response | None:
    for template, operations in contract()["paths"].items():
        pattern = re.sub(r"\\\{[^{}]+\\\}", "[^/]+", re.escape(template))
        if re.fullmatch(pattern, path):
            methods = {method.upper() for method in operations if method in {"get", "post", "put", "patch", "delete", "head", "options"}}
            if "OPTIONS" in methods:
                return None
            if "GET" in methods:
                methods.add("HEAD")
            methods.add("OPTIONS")
            return Response(media_type="text/html", headers={"Allow": ", ".join(sorted(methods))})
    return None


async def read_body(request: Request) -> dict[str, Any]:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json" and not (media_type.startswith("application/") and media_type.endswith("+json")):
        raise JsonMissing()
    limit = contract()["x-max-json-body-bytes"]
    try:
        declared_size = int(request.headers.get("content-length", "0"))
    except ValueError:
        declared_size = 0
    if declared_size > limit:
        raise PayloadTooLarge()
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise PayloadTooLarge()
        body.extend(chunk)
    try:
        value = json.loads(body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise JsonMissing() from None
    if value is None:
        raise JsonMissing()
    if not isinstance(value, dict):
        raise DictTypeError("body", value, dict, type(value), {})
    return value


@lru_cache(maxsize=256)
def parameter_definition(operation_id: str, location: str, name: str) -> dict[str, Any]:
    try:
        parameters = operation(operation_id)[3]
    except ValueError:
        raise RuntimeError(f"Undeclared parameter {operation_id}.{name}") from None
    return next(p for p in parameters if p["name"] == name and p["in"] == location)


def read_parameter(operation_id: str, location: str, name: str, value: Any, application_validated: bool = False) -> Any:
    parameter = parameter_definition(operation_id, location, name)
    schema = parameter["schema"]
    if value is None or value == []:
        if "default" in schema:
            return schema["default"]
        if parameter.get("required") and not application_validated:
            raise DictKeyError(name, {})
        return None
    if isinstance(value, list) and schema.get("type") != "array":
        value = value[0]
    try:
        if schema.get("type") == "integer":
            value = int(value)
        elif schema.get("type") == "number":
            value = float(value)
        elif schema.get("type") == "boolean":
            value = {"true": True, "false": False}[value]
    except (ValueError, KeyError, TypeError):
        raise SchemaValidationError(f"Invalid parameter '{name}'") from None
    error = next(OAS30Validator({"components": contract()["components"], **schema}).iter_errors(value), None)
    if error is not None:
        raise SchemaValidationError(f"Invalid parameter '{name}': {error.message}")
    if schema.get("format") in {"ip-address", "legacy-ip-address"}:
        try:
            return parse_ip_address(value)
        except ValueError:
            raise SchemaValidationError(f"Invalid IP address parameter '{name}'") from None
    return value


def render_response(result: ApiResponse[Any]) -> Response:
    if result.content_type != "application/json":
        return Response(result.body, status_code=result.status, media_type=result.content_type, headers=result.headers)
    return JSONResponse(to_wire(result.body), status_code=result.status, headers=result.headers)
