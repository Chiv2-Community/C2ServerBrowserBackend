from typing import List, Dict, Callable, TypeVar, Type, Generic, Any, Optional
import json
from dataclasses import dataclass

_A = TypeVar('_A')
_B = TypeVar('_B')

@dataclass(frozen=True)
class DictTypeError(Generic[_A, _B], Exception):
    key: str
    value: _B
    expected_type: Type[_A]
    actual_type: Type[_B]
    context: Dict[Any, Any]

@dataclass(frozen=True)
class DictKeyError(Generic[_A], Exception):
    key: str
    context: Dict[Any, Any]

def no_key_error(key: str, input_dict: Dict[str, Any]) -> Any:
    raise DictKeyError(key, input_dict)

def get_list_or(dictionary: Dict[str, Any], key: str, list_item_type: Type[_A], default: Optional[Callable[[], List[_A]]] = None) -> List[_A]:
    lst = get_or(dictionary, key, list, default)

    idx = 0
    for item in lst:
        if not isinstance(item, list_item_type):
            raise DictTypeError(key + f"[{idx}]", item, list_item_type, type(item), dictionary)
        idx += 1
        
    
    return lst

def get_or(dictionary: Dict[str, Any], key: str, expected_type: Type[_A], default: Optional[Callable[[], _A]] = None) -> _A:
    if key in dictionary:
        value = dictionary[key]
        if isinstance(value, expected_type):
            return value
        else:
            raise DictTypeError(key, value, expected_type, type(value), dictionary)

    if default is None:
        return no_key_error(key, dictionary)

    return default()

