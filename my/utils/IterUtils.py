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
        """
        Apply a sequence of functions to a value using reduce.

        Args:
            val: Initial value.
            *functions: Functions to apply in sequence.
        Returns:
            Final transformed value after applying all functions.
        """
        return ft.reduce(lambda acc, fn: fn(acc), functions, val)

    @classmethod
    def map_items(cls, value: object) -> list[tuple[Any, Any]]:
        """
        Extract key-value pairs from mapping-like or tuple sequence objects.

        Args:
            value: Object to extract items from (dict, mapping, or sequence of 2-tuples).
        Returns:
            List of (key, value) tuples, or empty list if extraction fails.
        """
        if not value:
            pass
        elif (fn := getattr(value, 'items', None)) and callable(fn):
            return list(fn())  # type:ignore
        elif isinstance(value, Series) and all(isinstance(v, tuple) and len(v) == 2 for v in value):
            return list(value)  # type: ignore
        return []

    @classmethod
    def partition(cls, items: Iterable[T], pred: Callable[[T], bool]) -> tuple[list[T], list[T]]:
        """
        Partition items into two lists based on a predicate.

        Args:
            items: Iterable to partition.
            pred: Predicate function (True items go to second list).
        Returns:
            Tuple of (items_failing_predicate, items_passing_predicate).
        """
        misses, hits = map(list, mi.partition(pred, items))
        return misses, hits

    @classmethod
    def multi_partition(
        cls, items: Iterable[T], **preds: Callable[[T], object]
    ) -> dict[str, list[T]]:
        """
        Partition items into multiple named buckets based on predicates.

        Args:
            items: Iterable to partition.
            **preds: Named predicates (keys become bucket names).
        Returns:
            Dict with predicate names as keys, plus 'rest' for unmatched items.
        Raises:
            AssertionError: If 'rest' is used as a predicate key name.
        """
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
        """
        Group items into buckets based on a key function.

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
    def find(
        cls, container: Sequence[Value], predicate: Callable[[Value], bool] | Value = bool
    ) -> int:
        """
        Find index of first item matching predicate or value.

        Args:
            container: Sequence to search.
            predicate: Predicate function or value to match (default: bool for truthiness).
        Returns:
            Index of first match, or -1 if not found.
        """
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
        Find the first key in the mapping for which the predicate on the corresponding value returns
        true.

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

        return next(
            (key for key, value in cls.map_items(items) if predicate(value)),  # type:ignore
            default,
        )

    @classmethod
    def next_in(cls, container: Container[Value], items: Iterable[Value]) -> Value | None:
        """
        Find first item from iterable that exists in container.

        Args:
            container: Container to check membership in.
            items: Items to check.
        Returns:
            First item found in container, or None.
        """
        return next(filter(container.__contains__, items), None)

    @classmethod
    def condense(cls, items: Iterable[T], pred: Callable[[T], bool] = bool) -> list[T]:
        """
        Filter items by predicate, returning list of matches.

        Args:
            items: Iterable to filter.
            pred: Predicate function (default: bool for truthiness).
        Returns:
            List of items matching predicate.
        """
        return list(filter(pred, items))

    @classmethod
    def map_condense(
        cls,
        items: Mapping[Key, Value] | Iterable[tuple[Key, Value]],
        pred: Callable[[Value], bool] = bool,
    ) -> Iterator[tuple[Key, Value]]:
        """
        Filter a mapping by a predicate function on values.

        Args:
            items: Mapping or iterable of (key, value) pairs to filter.
            pred: Predicate function applied to values (default: bool for truthiness).
        Yields:
            (key, value) tuples where value satisfies the predicate.
        """
        yield from filter(lambda tup: pred(tup[1]), cls.map_items(items))

    @classmethod
    def get_all(cls, dictionary: dict[str, T], *args: str, mandatory: bool = False) -> dict[str, T]:
        """
        Extract multiple keys from dictionary.

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
    def get_any(
        cls, dictionary: dict[str, T], *args: str, default: T | None = None, unique: bool = False
    ) -> T | None:
        """
        Get value for first matching key from dictionary.

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
        """
        Map a function over values in a mapping or iterable, returning new dictionary.

        Args:
            func: Function to apply to each value.
            data: Mapping, iterable of (key, value) pairs, or iterable of keys.
            drop: If True, drop falsy values from result (default: False).
        Returns:
            Dictionary with function applied to values (or to items if data is simple iterable).
        """
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
        """
        Extract attributes from object into dictionary.

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
    def chain_map(cls, funcs: Iterable[Callable[[T], C]], item: T) -> Iterator[C]:
        """
        Apply multiple functions to an item, yielding non-falsy results.

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
    def repeat_until_complete(cls, func: Callable[[C, T], tuple[int, T]]) -> Callable:
        """
        Decorator to repeatedly apply function until it returns 0 changes.

        Args:
            func: Function returning (num_changes, transformed_value).
        Returns:
            Wrapped function that repeats until num_changes is 0.
        """

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
        """
        Internal method to check container membership with any/all mode.

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
    def has_all(cls, container: Container[Value], *args: Value) -> bool:
        """
        Check if container contains all specified items.

        Args:
            container: Container to check.
            *args: Items that must all be present.
        Returns:
            True if all items present, False otherwise or if container empty.
        """
        return cls._has(container, *args, mode='all')

    @classmethod
    def has_any(cls, container: Container[Value], *args: Value) -> bool:
        """
        Check if container contains any of the specified items.

        Args:
            container: Container to check.
            *args: Items to check for (any match succeeds).
        Returns:
            True if any item present, False otherwise or if container empty.
        """
        return cls._has(container, *args, mode='any')

    @classmethod
    def has_only(cls, container: Collection[Value], *args: Value) -> bool:
        """
        Check if container contains exactly the specified items, no more no less.

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
    def has_none(cls, container: Container[Value], *args: Value) -> bool:
        """
        Check if container contains none of the specified items.

        Args:
            container: Container to check.
            *args: Items that must all be absent.
        Returns:
            True if no items present, False otherwise.
        """
        return not cls.has_any(container, *args)

    @classmethod
    def all_has_all(cls, containers: Iterable[Container[Value]], *args: Value) -> bool:
        """
        Check if all containers contain all specified items.

        Args:
            containers: Containers to check.
            *args: Items that must be in all containers.
        Returns:
            True if every container has all items, False otherwise or if empty.
        """
        return all(cls.has_all(cont, *args) for cont in containers) if containers else False

    @classmethod
    def any_has_all(cls, containers: Iterable[Container[Value]], *args: Value) -> bool:
        """
        Check if any container contains all specified items.

        Args:
            containers: Containers to check.
            *args: Items that must all be in at least one container.
        Returns:
            True if at least one container has all items, False otherwise or if empty.
        """
        return any(cls.has_all(cont, *args) for cont in containers) if containers else False

    @classmethod
    def all_has_any(cls, containers: Iterable[Container[Value]], *args: Value) -> bool:
        """
        Check if all containers contain at least one of the specified items.

        Args:
            containers: Containers to check.
            *args: Items (at least one must be in each container).
        Returns:
            True if every container has at least one item, False otherwise or if empty.
        """
        return all(cls.has_any(cont, *args) for cont in containers) if containers else False

    @classmethod
    def any_has_any(cls, containers: Iterable[Container[Value]], *args: Value) -> bool:
        """
        Check if any container contains any of the specified items.

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
        """
        Find longest common prefix of all strings.

        Args:
            *strings: Strings to compare.
        Returns:
            Longest common prefix string.
        """
        return ''.join(mi.longest_common_prefix(strings))

    @classmethod
    def shared_suffix(cls, *strings: str) -> str:
        """
        Find longest common suffix of all strings.

        Args:
            *strings: Strings to compare.
        Returns:
            Longest common suffix string.
        """
        return ''.join(reversed(list(mi.longest_common_prefix(map(reversed, strings)))))

    @classmethod
    def common_elements(cls, lhs: Sequence[T] | set[T], rhs: Sequence[T] | set[T]) -> list[T]:
        """
        Find elements common to both sequences, preserving multiplicities.

        Args:
            lhs: First sequence or set.
            rhs: Second sequence or set.
        Returns:
            List of common elements. For sequences, includes duplicates up to min count.
        """
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
        """
        Remove elements at specified indices from sequence.

        Args:
            data: Sequence to filter.
            mask: Indices to drop.
        Returns:
            List with elements at masked indices removed.
        """
        return [item for i, item in enumerate(data) if i not in mask]


iter_utils = IterUtils
"""An alias of `IterUtils`, cased so as to imply static usage."""
