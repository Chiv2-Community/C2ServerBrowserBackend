from typing import List, Dict, Callable, TypeVar, Type, Generic, Any
import json
from dataclasses import dataclass

A = TypeVar('A')
B = TypeVar('B')

@dataclass(frozen=True)
class DictTypeError(Generic[A, B], Exception):
    key: str
    value: B
    expected_type: Type[A]
    actual_type: Type[B]
    context: str

@dataclass(frozen=True)
class DictKeyError(Generic[A], Exception):
    key: str
    context: str

def default_error(key: str, input_dict: Dict[str, Any]) -> Any:
    raise DictKeyError(key, json.dumps(input_dict))

def get_or(dictionary: Dict[str, Any], key: str, expected_type: Type[A], default: Callable[[str, Dict[str, Any]], A] = default_error) -> A:
    if key in dictionary:
        value = dictionary[key]
        if isinstance(value, expected_type):
            return value
        else:
            raise DictTypeError(key, value, expected_type, type(value), json.dumps(dictionary))
    return default(key, dictionary)
