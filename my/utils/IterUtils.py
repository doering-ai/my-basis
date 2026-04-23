############
### HEAD ###
############
### STANDARD
from typing import Any, Literal, overload, TypeIs, Self, ClassVar
from collections.abc import (
    Callable,
    Collection,
    Container,
    Hashable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    MutableSequence,
)
from collections import Counter, defaultdict
import functools as ft
import contextlib as ctx

### EXTERNAL
import pydantic as pyd
import more_itertools as mi

### INTERNAL (NOTE: If adding new internal imports, update the comments in `__init__.py`)
from ..infra import Series, _Map


############
### DATA ###
############
type MapItems[K: Hashable, V] = Iterable[tuple[K, V]]
type Map[K: Hashable, V] = Mapping[K, V] | MapItems[K, V]


############
### BODY ###
############
class IterUtils:
    """Utility functions for working with iterators, sequences, mappings, and other containers."""

    # ----------------
    # `0` CONSTRUCTION
    # ----------------
    @classmethod
    def build[V](cls, val: V, *functions: Callable[[V], V]) -> V:
        """Apply a sequence of functions to a value using reduce.

        Args:
            val: Initial value.
            *functions: Functions to apply in sequence.
        Returns:
            Final transformed value after applying all functions.
        """
        return ft.reduce(lambda acc, fn: fn(acc), functions, val)

    @classmethod
    def map_items[K: Hashable | Any = Any, V = Any](
        cls,
        value: Mapping[K, V] | Iterable[tuple[K, V]],
    ) -> list[tuple[K, V]]:
        """Extract key-value pairs from mapping-like or tuple sequence objects.

        Args:
            value: Object to extract items from (dict, mapping, or sequence of 2-tuples).
        Returns:
            List of (key, value) tuples, or empty list if extraction fails.
        """
        if not value:
            pass
        elif (fn := getattr(value, 'items', None)) and callable(fn):
            return list(fn())  # type: ignore
        elif isinstance(value, Iterable):
            series = list(value)
            if all(isinstance(v, tuple) and len(v) == 2 for v in series):
                return series  # type: ignore
        return []

    @classmethod
    def is_map[K: Hashable | Any = Any, V = Any](
        cls,
        value: Mapping[K, V] | Iterable[tuple[K, V]] | object,
        ktype: type[K] | None = None,
        vtype: type[V] | None = None,
    ) -> TypeIs[Map[K, V]]:
        """Check if value is a map, or coercable to one. Can apply type checking.

        Args:
            value: Object to check.
            ktype: Optional type for keys.
            vtype: Optional type for values.
        Returns:
            True if value is mapping-like or sequence of 2-tuples, with optional type checks.
        """
        if value is None:
            return False

        _kt, _vt = ktype or object, vtype or object
        if isinstance(value, Mapping):
            return (all(isinstance(k, _kt) for k in value.keys())) and (
                all(isinstance(v, _vt) for v in value.values())
            )

        if isinstance(value, Iterator):
            value = list(value)

        if isinstance(value, Series):
            return all(
                isinstance(v, tuple)
                and len(v) == 2
                and isinstance(v[0], _kt)
                and isinstance(v[1], _vt)
                for v in value
            )
        return False

    @classmethod
    def partition[V](cls, items: Iterable[V], pred: Callable[[V], bool]) -> tuple[list[V], list[V]]:
        """Partition items into two lists based on a predicate.

        Args:
            items: Iterable to partition.
            pred: Predicate function (True items go to second list).
        Returns:
            Tuple of (items_failing_predicate, items_passing_predicate).
        """
        misses, hits = map(list, mi.partition(pred, items))
        return misses, hits

    @classmethod
    def multi_partition[V](
        cls, items: Iterable[V], **preds: Callable[[V], object]
    ) -> dict[str, list[V]]:
        """Partition items into multiple named buckets based on predicates.

        Args:
            items: Iterable to partition.
            **preds: Named predicates (keys become bucket names).
        Returns:
            Dict with predicate names as keys, plus 'rest' for unmatched items.
        Raises:
            AssertionError: If 'rest' is used as a predicate key name.
        """
        assert 'rest' not in preds.keys(), 'Cannot use key "rest" in multi_partition()'

        ret: dict[str, list[V]] = {key: [] for key in preds.keys()}
        ret['rest'] = list(items)
        for key, pred in preds.items():
            ret['rest'], ret[key] = map(list, mi.partition(pred, ret['rest']))
            if not ret['rest']:
                break
        return ret

    @classmethod
    def type_partition[T0, T1](
        cls, container: Iterable[T0 | T1], t0: type[T0], t1: type[T1]
    ) -> tuple[list[T0], list[T1]]:
        """Partition a container into two lists based on type."""
        ret = cls.multi_partition(
            container,
            t0=lambda x: isinstance(x, t0),
            t1=lambda x: isinstance(x, t1),
        )
        r0: list[T0] = ret.get('t0', [])  # type: ignore
        r1: list[T1] = ret.get('t1', [])  # type: ignore
        return r0, r1

    @classmethod
    def bucket[K: Hashable, T](cls, items: Iterable[T], pred: Callable[[T], K]) -> dict[K, list[T]]:
        """Group items into buckets based on a key function.

        Args:
            items: Iterable to bucket.
            pred: Function returning bucket key for each item.
        Returns:
            Defaultdict mapping bucket keys to lists of items.
        """
        buckets = mi.bucket(items, pred)
        return defaultdict(list, {key: list(buckets[key]) for key in buckets})

    # -------------
    # `1` SELECTION
    # -------------
    @classmethod
    def find[V](cls, container: Sequence[V], predicate: Callable[[V], bool] | V = bool) -> int:
        """Find index of first item matching predicate or value.

        Args:
            container: Sequence to search.
            predicate: Predicate function or value to match (default: bool for truthiness).
        Returns:
            Index of first match, or -1 if not found.
        """
        predicate = predicate if callable(predicate) else predicate.__eq__
        return next(mi.locate(container, predicate), -1)

    @classmethod
    def find_key[K: Hashable, V](
        cls,
        items: Mapping[K, V] | Iterable[tuple[K, V]],
        predicate: Callable[[V], bool] | V = bool,
        default: K | None = None,
    ) -> K | None:
        """Find the first key in a map whose value matches the provided predicate.

        Args:
            items: Mapping or iterable of (key, value) pairs to search.
            predicate: Predicate function or value to match (default: truthiness check).
            default: Default value to return if no match found (default: None).
        Returns:
            First matching key, or default if none found.
        """
        if not callable(predicate):
            cmp_obj = predicate
            predicate = lambda value: (cmp_obj == value) is True

        return next((key for key, value in cls.map_items(items) if predicate(value)), default)

    @classmethod
    def next_in[V](cls, container: Container[V], items: Iterable[V]) -> V | None:
        """Find first item from iterable that exists in container.

        Args:
            container: Container to check membership in.
            items: Items to check.
        Returns:
            First item found in container, or None.
        """
        return next(filter(container.__contains__, items), None)

    @classmethod
    def condense[V](cls, items: Iterable[V], pred: Callable[[V], bool] = bool) -> list[V]:
        """Filter items by predicate, returning list of matches.

        Args:
            items: Iterable to filter.
            pred: Predicate function (default: bool for truthiness).
        Returns:
            List of items matching predicate.
        """
        return list(filter(pred, items))

    @classmethod
    def map_condense[K: Hashable, V](
        cls, items: Mapping[K, V] | Iterable[tuple[K, V]], pred: Callable[[V], bool] = bool
    ) -> Iterator[tuple[K, V]]:
        """Filter a mapping by a predicate function on values.

        Args:
            items: Mapping or iterable of (key, value) pairs to filter.
            pred: Predicate function applied to values (default: bool for truthiness).
        Yields:
            (key, value) tuples where value satisfies the predicate.
        """
        yield from filter(lambda tup: pred(tup[1]), cls.map_items(items))

    @classmethod
    def get_all[K: Hashable, V](
        cls, dictionary: dict[K, V], *args: K, mandatory: bool = False
    ) -> dict[K, V]:
        """Extract multiple keys from dictionary.

        Args:
            dictionary: Dictionary to extract from.
            *args: Keys to extract.
            mandatory: If True, return empty dict unless all keys present (default: False).
        Returns:
            Dict with requested keys that exist, or empty dict if mandatory and any missing.
        """
        ret = {key: dictionary[key] for key in args if key in dictionary}
        if mandatory and len(ret) < len(args):
            return {}
        else:
            return ret

    @classmethod
    def get_any[K: Hashable, V](
        cls,
        dictionary: dict[K, V],
        *args: K,
        default: V | None = None,
        unique: bool = False,
    ) -> V | None:
        """Get value for first matching key from dictionary.

        Args:
            dictionary: Dictionary to search.
            *args: Keys to try in order.
            default: Default value if no keys found (default: None).
            unique: If True, raise error if multiple keys found (default: False).
        Returns:
            Value of first matching key, or default.
        Raises:
            ValueError: If unique=True and multiple keys match.
        """
        ret: dict[K, V] = {
            key: dictionary[key] for key in args if dictionary.get(key, default) != default
        }
        if len(ret) == 0:
            return default
        if len(ret) > 1 and unique:
            raise ValueError(f'Multiple keys found in dictionary: {ret.keys()}')
        else:
            return next(iter(ret.values()))

    @classmethod
    def safe[K: Hashable = str, V = str](
        cls, container: _Map[K, V | Map | None], *keys: K
    ) -> V | None:
        """Safely access nested map values with multiple keys.

        Args:
            container: Map to access.
            *keys: Sequence of keys to traverse.
        Returns:
            Value at nested location if all keys exist, else None.
        """
        cur: V | dict[K, Any] | None = dict(container)

        for key in keys:
            if isinstance(cur, dict):
                if key in cur:
                    cur = cur[key]
                else:
                    return None
            else:
                return cur
        return cur  # type: ignore

    # ---------------
    # `2` APPLICATION
    # ---------------
    @overload
    @classmethod
    def val_map[K: Hashable, T0, T1](
        cls,
        func: Callable[[T0], T1],
        data: Mapping[K, T0] | Iterable[tuple[K, T0]],
        drop: bool = False,
    ) -> dict[K, T1]: ...

    @overload
    @classmethod
    def val_map[K: Hashable, T1](
        cls,
        func: Callable[[K], T1],
        data: Iterable[K],
        drop: bool = False,
    ) -> dict[K, T1]: ...

    @classmethod
    def val_map[K: Hashable, T0, T1](
        cls,
        func: Callable[[T0], T1] | Callable[[K], T1],
        data: Mapping[K, T0] | Iterable[tuple[K, T0]] | Iterable[K],
        drop=False,
    ) -> dict:
        """Map a function over values in a mapping or iterable, returning new dictionary.

        Args:
            func: Function to apply to each value.
            data: Mapping, iterable of (key, value) pairs, or iterable of keys.
            drop: If True, drop falsy values from result (default: False).
        Returns:
            Dictionary with function applied to values (or to items if data is simple iterable).
        """
        if not data:
            return {}
        elif cls.is_map(data):
            ret = {key: func(val) for key, val in cls.map_items(data)}  # type: ignore
        else:
            ret = {key: func(key) for key in data}  # type:ignore

        if drop:
            ret = {key: val for key, val in ret.items() if key and val}
        return ret  # type:ignore

    @classmethod
    def attr_map(cls, obj: object, fields: Iterable[str], drop: bool = False) -> dict[str, Any]:
        """Extract attributes from object into dictionary.

        Args:
            obj: Object to extract attributes from.
            fields: Attribute names to extract.
            drop: If True, drop falsy values and use default='' (default: False).
        Returns:
            Dict mapping field names to attribute values.
        """
        fn = ft.partial(getattr, obj, **(dict(default='') if drop else dict()))
        return cls.val_map(fn, {f: f for f in fields}, drop)

    @classmethod
    def chain_map[V, R](cls, funcs: Iterable[Callable[[V], R]], item: V) -> Iterator[R]:
        """Apply multiple functions to an item, yielding non-falsy results.

        Args:
            funcs: Functions to apply.
            item: Item to pass to each function.
        Yields:
            Non-falsy results from function applications.
        """
        for func in funcs:
            if ret := func(item):
                yield ret

    # -------------
    # `3` EXECUTION
    # -------------
    @classmethod
    def repeat_until_complete[C, V](cls, func: Callable[[C, V], tuple[int, V]]) -> Callable:
        """Decorator to repeatedly apply function until it returns 0 changes.

        Args:
            func: Function returning (num_changes, transformed_value).
        Returns:
            Wrapped function that repeats until num_changes is 0.
        """

        @ft.wraps(func)
        def wrapper(cls: C, value: V, **kwargs: Any) -> tuple[int, V]:
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
        """Internal method to check container membership with any/all mode.

        Args:
            container: Container to check.
            *args: Items to check for.
            mode: 'any' or 'all' for membership test (default: 'any').
        Returns:
            True if mode condition met, False if container empty or condition fails.
        """
        fn = any if mode == 'any' else all
        return fn(arg in container for arg in args) if container else False

    @classmethod
    def has_all[V](cls, container: Container[V], *args: V) -> bool:
        """Check if container contains all specified items.

        Args:
            container: Container to check.
            *args: Items that must all be present.
        Returns:
            True if all items present, False otherwise or if container empty.
        """
        return cls._has(container, *args, mode='all')

    @classmethod
    def has_any[V](cls, container: Container[V], *args: V) -> bool:
        """Check if container contains any of the specified items.

        Args:
            container: Container to check.
            *args: Items to check for (any match succeeds).
        Returns:
            True if any item present, False otherwise or if container empty.
        """
        return cls._has(container, *args, mode='any')

    @classmethod
    def has_only[V](cls, container: Collection[V], *args: V) -> bool:
        """Check if container contains exactly the specified items, no more no less.

        Args:
            container: Collection to check.
            *args: Items that should comprise the entire collection.
        Returns:
            True if container contains exactly these items.
        """
        if isinstance(container, str):
            return len(container) == sum(map(len, args)) and cls.has_all(container, *args)  # type:ignore
        return set(container) == set(args)

    @classmethod
    def has_none[V](cls, container: Container[V], *args: V) -> bool:
        """Check if container contains none of the specified items.

        Args:
            container: Container to check.
            *args: Items that must all be absent.
        Returns:
            True if no items present, False otherwise.
        """
        return not cls.has_any(container, *args)

    @classmethod
    def all_has_all[V](cls, containers: Iterable[Container[V]], *args: V) -> bool:
        """Check if all containers contain all specified items.

        Args:
            containers: Containers to check.
            *args: Items that must be in all containers.
        Returns:
            True if every container has all items, False otherwise or if empty.
        """
        return all(cls.has_all(cont, *args) for cont in containers) if containers else False

    @classmethod
    def any_has_all[V](cls, containers: Iterable[Container[V]], *args: V) -> bool:
        """Check if any container contains all specified items.

        Args:
            containers: Containers to check.
            *args: Items that must all be in at least one container.
        Returns:
            True if at least one container has all items, False otherwise or if empty.
        """
        return any(cls.has_all(cont, *args) for cont in containers) if containers else False

    @classmethod
    def all_has_any[V](cls, containers: Iterable[Container[V]], *args: V) -> bool:
        """Check if all containers contain at least one of the specified items.

        Args:
            containers: Containers to check.
            *args: Items (at least one must be in each container).
        Returns:
            True if every container has at least one item, False otherwise or if empty.
        """
        return all(cls.has_any(cont, *args) for cont in containers) if containers else False

    @classmethod
    def any_has_any[V](cls, containers: Iterable[Container[V]], *args: V) -> bool:
        """Check if any container contains any of the specified items.

        Args:
            containers: Containers to check.
            *args: Items to look for.
        Returns:
            True if at least one container has at least one item, False otherwise or if empty.
        """
        return any(cls.has_any(cont, *args) for cont in containers) if containers else False

    # --------------
    # `5` COMPARISON
    # --------------
    @classmethod
    def shared_prefix(cls, *strings: str) -> str:
        """Find longest common prefix of all strings.

        Args:
            *strings: Strings to compare.
        Returns:
            Longest common prefix string.
        """
        return ''.join(mi.longest_common_prefix(strings))

    @classmethod
    def shared_suffix(cls, *strings: str) -> str:
        """Find longest common suffix of all strings.

        Args:
            *strings: Strings to compare.
        Returns:
            Longest common suffix string.
        """
        return ''.join(reversed(list(mi.longest_common_prefix(map(reversed, strings)))))

    @classmethod
    def common_elements[V: Hashable](
        cls,
        lhs: Sequence[V] | set[V],
        rhs: Sequence[V] | set[V],
    ) -> list[V]:
        """Return a version of the first sequence with only values found in the second.

        Treats repeated elements according to their counts in each sequence.

        ```python
        assert common_elements([9, 1, 3, 9, 9], [1, 9, 9]) == [9, 1, 9]
        ```

        Args:
            lhs: First sequence or set.
            rhs: Second sequence or set.
        Returns:
            List of common elements. For sequences, includes duplicates.
        """
        if isinstance(lhs, set) or isinstance(rhs, set):
            return list(set(lhs) & set(rhs))
        else:
            counter = Counter(rhs)
            ret = []
            for value in lhs:
                if counter[value]:
                    ret.append(value)
                    counter[value] -= 1
            return ret

    @classmethod
    def exclusive_elements[H: Hashable, S: Sequence = list](
        cls,
        lhs: S,
        rhs: Iterable[H],
    ) -> S:
        """Return a version of the first sequence with only values NOT found in the second.

        Treats repeated elements according to their counts in each sequence.

        ```python
        assert common_elements([9, 1, 3, 9, 9], [1, 9, 9]) == [3, 9]
        ```

        Args:
            lhs: First sequence or set.
            rhs: Second sequence or set.
        Returns:
            List of exclusive elements.
        """
        tvar = type(lhs)
        counter = Counter(rhs)
        ret = []
        for value in lhs:
            if counter[value] <= 0:
                ret.append(value)
                counter[value] -= 1
        return tvar(ret)  # type: ignore

    # ----------------
    # `6` MODIFICATION
    # ----------------
    @classmethod
    def drop_at[V](cls, data: Sequence[V], mask: Iterable[int]) -> list[V]:
        """Remove elements at specified indices from sequence.

        Args:
            data: Sequence to filter.
            mask: Indices to drop.
        Returns:
            List with elements at masked indices removed.
        """
        if not mask:
            return list(data)
        return [item for i, item in enumerate(data) if i not in mask]

    @classmethod
    def drop_duplicates(cls, data: MutableSequence) -> None:
        """Remove duplicate elements from a list, preserving order.

        Args:
            data: Iterable to process.
        """
        seen: set = set()
        to_drop = []
        for i, item in enumerate(data):
            if item not in seen:
                seen.add(item)
            else:
                to_drop.append(i)

        if to_drop:
            for index in reversed(to_drop):
                del data[index]


iter_utils = IterUtils
