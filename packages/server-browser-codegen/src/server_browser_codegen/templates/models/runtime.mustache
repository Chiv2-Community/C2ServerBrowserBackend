"""Generated model support. DO NOT EDIT; change server-browser-codegen templates."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from ipaddress import IPv4Address, IPv6Address, ip_address
import json
from typing import Annotated, Any, TypeVar, get_args, get_origin
from types import UnionType
from typing import Union

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer, TypeAdapter, ValidationError
from openapi_schema_validator import OAS30Validator

T = TypeVar("T", bound="WireModel")


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


class SchemaValidationError(ValueError):
    pass


@lru_cache(maxsize=1)
def contract() -> dict[str, Any]:
    return json.loads(files("server_browser_models").joinpath("contract.json").read_text())


@lru_cache(maxsize=None)
def operation(operation_id: str) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]]:
    for path, entry in contract()["paths"].items():
        for method, declaration in entry.items():
            if isinstance(declaration, dict) and declaration.get("operationId") == operation_id:
                return method.upper(), path, declaration, entry.get("parameters", []) + declaration.get("parameters", [])
    raise ValueError(f"Unknown operation {operation_id}")


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
        for name, definition in cls.model_fields.items():
            key = definition.alias or name
            metadata = definition.json_schema_extra or {}
            assert isinstance(metadata, dict)
            if key not in value:
                if definition.is_required():
                    raise DictKeyError(key, value)
                continue
            annotation = definition.rebuild_annotation()
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


def to_wire(value: Any) -> Any:
    return TypeAdapter(Any).dump_python(value, mode="json", by_alias=True)
