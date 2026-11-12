"""Generated transport support. DO NOT EDIT; change codegen/templates instead."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from ipaddress import IPv4Address, IPv6Address, ip_address
import json
import re
from typing import Annotated, Any, Generic, TypeVar, get_args, get_origin, get_type_hints
from types import UnionType
from typing import Union

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder as to_wire
from starlette.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer, TypeAdapter, ValidationError
from openapi_schema_validator import OAS30Validator

T = TypeVar("T", bound="WireModel")
R = TypeVar("R")


def parse_ip_address(value: Any) -> IPv4Address | IPv6Address:
    if isinstance(value, (IPv4Address, IPv6Address)):
        return value
    if not isinstance(value, str):
        raise ValueError("Expected an IPv4 or IPv6 address string")
    if value.startswith("[") and value.endswith("]"):
        return IPv6Address(value[1:-1])
    return ip_address(value)


def legacy_ip_address(value: IPv4Address | IPv6Address) -> str:
    return f"[{value}]" if isinstance(value, IPv6Address) else str(value)


IPAddress = Annotated[
    IPv4Address | IPv6Address,
    BeforeValidator(parse_ip_address),
    PlainSerializer(str, return_type=str),
]
LegacyIPAddress = Annotated[
    IPv4Address | IPv6Address,
    BeforeValidator(parse_ip_address),
    PlainSerializer(legacy_ip_address, return_type=str),
]


class JsonMissing(Exception):
    pass


class SchemaValidationError(ValueError):
    pass


@lru_cache(maxsize=1)
def contract() -> dict[str, Any]:
    return json.loads(files("server_browser_api").joinpath("contract.json").read_text())


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


@lru_cache(maxsize=256)
def validator(model_name: str) -> OAS30Validator:
    return OAS30Validator({
        "components": contract()["components"],
        "$ref": f"#/components/schemas/{model_name}",
    })


@dataclass
class DictKeyError(Exception):
    key: str
    context: dict[str, Any]


@dataclass
class DictTypeError(Exception):
    key: str
    value: Any
    expected_type: type
    actual_type: type
    context: dict[str, Any]


async def read_body(request: Request) -> dict[str, Any]:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json" and not (media_type.startswith("application/") and media_type.endswith("+json")):
        raise JsonMissing()
    try:
        value = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise JsonMissing() from None
    if value is None:
        raise JsonMissing()
    if not isinstance(value, dict):
        raise DictTypeError("body", value, dict, type(value), {})
    return value


def read_parameter(operation_id: str, location: str, name: str, value: Any, application_validated: bool = False) -> Any:
    for path in contract()["paths"].values():
        for operation in path.values():
            if not isinstance(operation, dict) or operation.get("operationId") != operation_id:
                continue
            parameters = path.get("parameters", []) + operation.get("parameters", [])
            parameter = next(p for p in parameters if p["name"] == name and p["in"] == location)
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
    raise RuntimeError(f"Undeclared parameter {operation_id}.{name}")


def decode(annotation: Any, value: Any, key: str, context: dict[str, Any]) -> Any:
    origin = get_origin(annotation)
    if origin is Annotated:
        try:
            return TypeAdapter(annotation).validate_python(value)
        except ValidationError:
            raise DictTypeError(key, value, str, type(value), context) from None
    if origin in (Union, UnionType):
        if value is None and type(None) in get_args(annotation):
            return None
        candidates = sorted(get_args(annotation), key=lambda candidate: len(candidate.model_fields) if isinstance(candidate, type) and issubclass(candidate, BaseModel) else 0, reverse=True)
        for candidate in candidates:
            if candidate is not type(None):
                try:
                    return decode(candidate, value, key, context)
                except (DictTypeError, DictKeyError, SchemaValidationError):
                    pass
        raise DictTypeError(key, value, get_args(annotation)[0], type(value), context)
    expected = origin or annotation
    if annotation is Any:
        return value
    if annotation is float and isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(expected, type) and issubclass(expected, WireModel):
        if not isinstance(value, dict):
            raise DictTypeError(key, value, dict, type(value), context)
        return expected.from_json(value)
    if not isinstance(value, expected):
        raise DictTypeError(key, value, expected, type(value), context)
    if origin is list:
        return [decode(get_args(annotation)[0], item, f"{key}[{index}]", context) for index, item in enumerate(value)]
    return value


class WireModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, populate_by_name=True)

    @classmethod
    def from_json(cls: type[T], value: dict[str, Any]) -> T:
        arguments: dict[str, Any] = {}
        hints = get_type_hints(cls, include_extras=True)
        for name, definition in cls.model_fields.items():
            key = definition.alias or name
            metadata = definition.json_schema_extra or {}
            assert isinstance(metadata, dict)
            if key not in value:
                if definition.is_required():
                    raise DictKeyError(key, value)
                continue
            annotation = hints[name]
            if value[key] is None and not metadata["nullable"]:
                expected = get_args(annotation)[0] if get_origin(annotation) in (Union, UnionType) else annotation
                if get_origin(expected) is Annotated:
                    expected = str
                raise DictTypeError(key, None, get_origin(expected) or expected, type(None), value)
            decoded = decode(annotation, value[key], key, value)
            arguments[name] = decoded
        error = next(validator(cls.__name__).iter_errors(value), None)
        if error is not None:
            raise SchemaValidationError(error.message)
        return cls(**arguments)


def decode_model(model: type[T], value: dict[str, Any]) -> T:
    return model.from_json(value)


@dataclass(frozen=True)
class ApiResponse(Generic[R]):
    body: R
    status: int = 200
    content_type: str = "application/json"


def render_response(result: ApiResponse[Any]) -> Response:
    if result.content_type != "application/json":
        return Response(result.body, status_code=result.status, media_type=result.content_type)
    return JSONResponse(to_wire(result.body), status_code=result.status)
