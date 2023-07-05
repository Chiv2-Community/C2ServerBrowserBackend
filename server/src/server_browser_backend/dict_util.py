from typing import List, Dict, Callable, TypeVar, Type

A = TypeVar('A')

def default_error(key: str) -> A:
    raise TypeError(f"Key '{key}' not found")

def get_or(dictionary: Dict[str, any], key: str, expected_type: Type[A], default: Callable[[str], A] = default_error) -> A:
    if key in dictionary:
        value = dictionary[key]
        if isinstance(value, expected_type):
            return value
        else:
            raise TypeError(f"Expected type {expected_type} for key {key} but got {type(value)}")
    return default(key)
