from typing import List, Dict, Callable, TypeVar, Type, Generic, Any, Optional
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
    context: Dict[Any, Any]

@dataclass(frozen=True)
class DictKeyError(Generic[A], Exception):
    key: str
    context: Dict[Any, Any]

def no_key_error(key: str, input_dict: Dict[str, Any]) -> Any:
    raise DictKeyError(key, input_dict)

def get_or(dictionary: Dict[str, Any], key: str, expected_type: Type[A], default: Optional[Callable[[], A]] = None) -> A:
    if key in dictionary:
        value = dictionary[key]
        if isinstance(value, expected_type):
            return value
        else:
            raise DictTypeError(key, value, expected_type, type(value), dictionary)

    if default is None:
        return no_key_error(key, dictionary)

    return default()

