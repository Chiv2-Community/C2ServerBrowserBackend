from server_browser_backend.iterable_util import find


def test_find_first_match():
    assert find([1, 2, 4], lambda item: item % 2 == 0) == 2


def test_find_no_match():
    assert find([1, 3], lambda item: item % 2 == 0) is None


def test_find_empty():
    assert find([], lambda item: True) is None


def test_find_falsy_match():
    assert find([1, 0, 2], lambda item: item == 0) == 0


def test_find_stops_iterator_at_match():
    items = iter([1, 2, 3])
    assert find(items, lambda item: item == 2) == 2
    assert next(items) == 3
