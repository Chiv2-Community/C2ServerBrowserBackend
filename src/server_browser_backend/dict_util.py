from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, List, Optional, Type

from server_browser_backend.type_vars import A, B


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


def _no_key_error(key: str, input_dict: Dict[str, Any]) -> Any:
    raise DictKeyError(key, input_dict)


def get_list_or(
    dictionary: Dict[str, Any],
    key: str,
    list_item_type: Type[A],
    default: Optional[Callable[[], List[A]]] = None,
) -> List[A]:
    """Gets a list from the dictionary, and checks that all items in the list are of the correct type"""
    lst = get_or(dictionary, key, list, default)

    idx = 0
    for item in lst:
        if not isinstance(item, list_item_type):
            raise DictTypeError(
                key + f"[{idx}]", item, list_item_type, type(item), dictionary
            )
        idx += 1

    return lst


def get_or(
    dictionary: Dict[str, Any],
    key: str,
    expected_type: Type[A],
    default: Optional[Callable[[], A]] = None,
) -> A:
    """Gets a value from the dictionary and checks that it is of the correct type"""
    if key in dictionary:
        value = dictionary[key]
        if isinstance(value, expected_type):
            return value
        else:
            raise DictTypeError(key, value, expected_type, type(value), dictionary)

    if default is None:
        return _no_key_error(key, dictionary)

    return default()

def get_or_optional(
    dictionary: Dict[str, Any],
    key: str,
    expected_type: Type[A],
) -> Optional[A]:
    """Gets a value from the dictionary and checks that it is of the correct type. Returns None if the key is not present."""
    if key in dictionary:
        value = dictionary[key]
        if isinstance(value, expected_type):
            return value
        else:
            raise DictTypeError(key, value, expected_type, type(value), dictionary)
    return None

def get_list_or_optional(
        dictionary: Dict[str, Any],
        key: str,
        list_item_type: Type[A]
) -> Optional[List[A]]:
    """Gets a list from the dictionary, and checks that all items in the list are of the correct type. Returns None if the key is not present."""
    if key in dictionary:
        return get_list_or(dictionary, key, list_item_type)
    return None