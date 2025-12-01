############
### HEAD ###
############
### STANDARD
from typing import (
    Any,
    Callable,
    Collection,
    Container,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    Sequence,
)
from collections import Counter, defaultdict
import functools as ft

### EXTERNAL
import more_itertools as mi

### INTERNAL
from ..infra import T, C, Key, Value, Series


############
### BODY ###
############
class IterUtils:
    """
    A collection of utility functions for working with iterables, mappings, and containers.
    """

    # ----------------
    # `0` CONSTRUCTION
    # ----------------
    @classmethod
    def build(cls, val: Value, *functions: Callable[[Value], Value]) -> Value:
        return ft.reduce(lambda acc, fn: fn(acc), functions, val)

    @classmethod
    def map_items(cls, value: object) -> list[tuple[Any, Any]]:
        if not value:
            pass
        elif (fn := getattr(value, 'items', None)) and callable(fn):
            return list(fn())  # type:ignore
        elif isinstance(value, Series) and all(isinstance(v, tuple) and len(v) == 2 for v in value):
            return list(value)  # type: ignore
        return []

    @classmethod
    def partition(cls, items: Iterable[T], pred: Callable[[T], bool]) -> tuple[list[T], list[T]]:
        misses, hits = map(list, mi.partition(pred, items))
        return misses, hits

    @classmethod
    def multi_partition(
        cls, items: Iterable[T], **preds: Callable[[T], object]
    ) -> dict[str, list[T]]:
        assert 'rest' not in preds.keys(), 'Cannot use key "rest" in multi_partition()'

        ret: dict[str, list[T]] = {key: [] for key in preds.keys()}
        ret['rest'] = list(items)
        for key, pred in preds.items():
            ret['rest'], ret[key] = map(list, mi.partition(pred, ret['rest']))
            if not ret['rest']:
                break
        return ret

    @classmethod
    def bucket(cls, items: Iterable[T], pred: Callable[[T], C]) -> dict[C, list[T]]:
        buckets = mi.bucket(items, pred)
        return defaultdict(list, {key: list(buckets[key]) for key in buckets})

    # -------------
    # `1` SELECTION
    # -------------
    @classmethod
    def find(
        cls, container: Sequence[Value], predicate: Callable[[Value], bool] | Value = bool
    ) -> int:
        predicate = predicate if callable(predicate) else predicate.__eq__
        return next(mi.locate(container, predicate), -1)

    @classmethod
    def find_key(
        cls,
        items: Mapping[Key, Value] | Iterable[tuple[Key, Value]],
        predicate: Callable[[Value], bool] | Value = bool,
        default: Key | None = None,
    ) -> Key | None:
        """
        Find the first key in the mapping for which the predicate returns True.
        If no such key exists, return None.
        """
        predicate = predicate if callable(predicate) else predicate.__eq__
        return next(
            (key for key, value in cls.map_items(items) if predicate(value)),  # type:ignore
            default,
        )

    @classmethod
    def next_in(cls, container: Container[Value], items: Iterable[Value]) -> Value | None:
        return next(filter(container.__contains__, items), None)

    @classmethod
    def condense(cls, items: Iterable[T], pred: Callable[[T], bool] = bool) -> list[T]:
        return list(filter(pred, items))

    @classmethod
    def map_condense(
        cls,
        items: Mapping[Key, Value] | Iterable[tuple[Key, Value]],
        pred: Callable[[Value], bool] = bool,
    ) -> Iterator[tuple[Key, Value]]:
        """Filter a mapping by a predicate function."""
        yield from filter(lambda tup: pred(tup[1]), cls.map_items(items))

    @classmethod
    def get_all(cls, dictionary: dict[str, T], *args: str, mandatory: bool = False) -> dict[str, T]:
        ret = {key: dictionary[key] for key in args if key in dictionary}
        if mandatory and len(ret) < len(args):
            return {}
        else:
            return ret

    @classmethod
    def get_any(
        cls, dictionary: dict[str, T], *args: str, default: T | None = None, unique: bool = False
    ) -> T | None:
        ret: dict[str, T] = {
            key: dictionary[key] for key in args if dictionary.get(key, default) != default
        }
        if len(ret) == 0:
            return default
        if len(ret) > 1 and unique:
            raise ValueError(f'Multiple keys found in dictionary: {ret.keys()}')
        else:
            return list(ret.values())[0]

    # ---------------
    # `2` APPLICATION
    # ---------------
    @classmethod
    def val_map(
        cls,
        func: Callable[[Value], T],
        data: Mapping[Key, Value] | Iterable[tuple[Key, Value]] | Iterable[Key],
        drop: bool = False,
    ) -> dict[Key, T]:
        """Map a function over the values of a mapping or iterable, returning a new dictionary."""
        if not data:
            return {}
        elif items := cls.map_items(data):  # type:ignore
            ret = {key: func(val) for key, val in items}  # type:ignore
        else:
            ret = {val: func(val) for val in data}  # type:ignore

        if drop:
            ret = dict(filter(all, ret.items()))
        return ret  # type:ignore

    @classmethod
    def attr_map(cls, obj: object, fields: Iterable[str], drop: bool = False) -> dict[str, Any]:
        fn = ft.partial(getattr, obj, **(dict(default='') if drop else dict()))
        return cls.val_map(fn, {f: f for f in fields}, drop)

    @classmethod
    def chain_map(cls, funcs: Iterable[Callable[[T], C]], item: T) -> Iterator[C]:
        for func in funcs:
            if ret := func(item):
                yield ret

    # -------------
    # `3` EXECUTION
    # -------------
    @classmethod
    def repeat_until_complete(cls, func: Callable[[C, T], tuple[int, T]]) -> Callable:
        @ft.wraps(func)
        def wrapper(cls: C, value: T, **kwargs: Any) -> tuple[int, T]:
            run_results: list[int] = []
            while not run_results or run_results[-1] > 0:
                num_changes, value = func(cls, value, **kwargs)
                run_results.append(num_changes)

            return sum(run_results), value

        return wrapper

    # ------------
    # `4` PRESENCE
    # ------------
    @classmethod
    def _has(cls, container: Container, *args: Any, mode: Literal['any', 'all'] = 'any') -> bool:
        fn = any if mode == 'any' else all
        return fn(arg in container for arg in args) if container else False

    @classmethod
    def has_all(cls, container: Container[Value], *args: Value) -> bool:
        return cls._has(container, *args, mode='all')

    @classmethod
    def has_any(cls, container: Container[Value], *args: Value) -> bool:
        return cls._has(container, *args, mode='any')

    @classmethod
    def has_only(cls, container: Collection[Value], *args: Value) -> bool:
        if isinstance(container, str):
            return len(container) == sum(map(len, args)) and cls.has_all(container, *args)  # type:ignore
        return set(container) == set(args)

    @classmethod
    def has_none(cls, container: Container[Value], *args: Value) -> bool:
        return not cls.has_any(container, *args)

    @classmethod
    def all_has_all(cls, containers: Iterable[Container[Value]], *args: Value) -> bool:
        return all(cls.has_all(cont, *args) for cont in containers) if containers else False

    @classmethod
    def any_has_all(cls, containers: Iterable[Container[Value]], *args: Value) -> bool:
        return any(cls.has_all(cont, *args) for cont in containers) if containers else False

    @classmethod
    def all_has_any(cls, containers: Iterable[Container[Value]], *args: Value) -> bool:
        return all(cls.has_any(cont, *args) for cont in containers) if containers else False

    @classmethod
    def any_has_any(cls, containers: Iterable[Container[Value]], *args: Value) -> bool:
        return any(cls.has_any(cont, *args) for cont in containers) if containers else False

    # --------------
    # `5` COMPARISON
    # --------------
    @classmethod
    def shared_prefix(cls, *strings: str) -> str:
        return ''.join(mi.longest_common_prefix(strings))

    @classmethod
    def shared_suffix(cls, *strings: str) -> str:
        return ''.join(reversed(list(mi.longest_common_prefix(map(reversed, strings)))))

    @classmethod
    def common_elements(cls, lhs: Sequence[T] | set[T], rhs: Sequence[T] | set[T]) -> list[T]:
        if isinstance(lhs, set) or isinstance(rhs, set):
            return list(set(lhs) & set(rhs))
        else:
            c0, c1 = Counter(lhs), Counter(rhs)
            shared = set(c0.keys()) & set(c1.keys())
            return [val for val in shared for _ in range(min(c0[val], c1[val]))]

    # ----------------
    # `6` MODIFICATION
    # ----------------
    @classmethod
    def drop_at(cls, data: Sequence[T], mask: Iterable[int]) -> list[T]:
        return [item for i, item in enumerate(data) if i not in mask]


iter_utils = IterUtils
