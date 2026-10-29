from typing import Callable, Iterable, Optional

from server_browser_backend.type_vars import A


def find(items: Iterable[A], predicate: Callable[[A], bool]) -> Optional[A]:
    """Return the first matching item, or None."""
    return next((item for item in items if predicate(item)), None)
