from typing import Any
import typing
from collections import deque
from collections.abc import Hashable, Iterable, Iterator, Mapping, Iterable
from .Typist import typist
from ..infra import Series, _Series, Map, _Map
from ..types import Predicate


json_data = '{"data": "here"}'

_dict = typist.from_json(json_data)
typing.assert_type(_dict, dict)

second = typist.from_json(json_data, list[dict])
typing.assert_type(second, list[dict])

error: int = '555555'


pred1 = Predicate.new(dict(a=[5]))
pred2 = Predicate.new(b=[1, 2, 3], c=[4, 5, 6])
dict1 = dict(d=[7, 88, 999])
dict2: dict[str, list[int]] = dict(d=[7, 88, 999])
dict3: dict = dict(d=[7, 88, 999])
dict4: dict[str, Any] = dict(d=[7, 88, 999])
items = [('e', [10]), ('f', [11, 12, 13])]
items2: list[tuple[str, list[int]]] = [('e', [10]), ('f', [11, 12, 13])]


type SeriesTwo[V] = list[V] | tuple[V, ...] | set[V] | deque[V]

MapPlain = Mapping | Iterable


type MapType[K: Hashable, V] = Mapping[K, V] | Iterable[tuple[K, V]]


def _bar(data: dict[str, str] | dict[str, int] | set[float]) -> None:
    typing.assert_type(data, dict[str, str] | dict[str, int] | set[float])

    if typist.check(data, dict[str, str] | dict[str, int]):
        typing.assert_type(data, dict)

    elif typist.check(data, set[float]):
        typing.assert_type(data, set[float])


def _foo(data: MapType[str, list[int]]) -> Map:
    assert isinstance(data, MapPlain)
    assert typist.check(data, MapPlain)

    typing.assert_type(data, MapPlain)

    if isinstance(data, dict):
        typing.assert_type(data, dict[str, list[int]])
    else:
        typing.assert_type(data, list[tuple[str, list[int]]])
    return data


err2: str = 5

_foo(pred2)
_foo(dict1)
_foo(dict2)
_foo(dict3)
_foo(dict4)
_foo(items)
_foo(items2)


# Add
pred1 += pred2
pred1 += dict1
pred1 += dict2
pred1 += items

# Or
pred1 |= pred2
pred1 |= dict1
pred1 |= dict2
pred1 |= items

# And
pred1 &= {'1', '2', '3'}
pred1 &= pred2
pred1 &= dict1
pred1 &= dict2
pred1 &= items

# Sub
pred1 -= pred2
pred1 -= dict1
pred1 -= dict2
pred1 -= items
