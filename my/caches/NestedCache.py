############
### HEAD ###
############
### STANDARD
from typing import Any, cast
from collections.abc import Hashable, Iterator
import functools as ft
import math

### EXTERNAL
import pydantic as pyd

### INTERNAL


############
### DATA ###
############
#: Sentinel distinguishing "key absent" from a legitimately-stored falsy/None value, so
#: concurrent-safe `pop(key, _MISSING)` eviction can count real removals without a membership
#: pre-check (which would race with a concurrent delete).
_MISSING: Any = object()


############
### BODY ###
############
class NestedCache[Keys: tuple, Value](pyd.BaseModel):
    """Multi-level hierarchical cache with automatic pruning.

    Supports arbitrary nesting depth determined by the signature tuple length.
    Each level maintains LRU ordering. Pruning is distributed proportionally
    across child caches based on their sizes.

    Examples:
        Store and retrieve values under two-level key paths::

            >>> from my import NestedCache
            >>> cache = NestedCache(signature=(str, int))
            >>> cache[('user', 1)] = 'robb'
            >>> cache.set(('user', 2), 'ada')
            1
            >>> cache[('user', 1)]
            'robb'
            >>> len(cache)
            2
            >>> cache.delete(('user', 2))
            1
    """

    signature: tuple[type, ...]

    children: dict[Hashable, 'NestedCache'] = {}
    data: dict[Any, Value] = {}
    size: int = 0

    max_size: int = pyd.Field(default=2**12, gt=0)  # 4096
    bucket_size: int = pyd.Field(default=2**8, gt=0)  # 256

    @ft.cached_property
    def depth(self) -> int:
        """The number of key levels in this cache (i.e. the length of its signature)."""
        return len(self.signature)

    def __getitem__(self, keys: list | tuple) -> Value | None:
        if len(keys) != self.depth:
            return None

        key, *keys = keys
        if self.depth == 1:
            val = self.data.pop(key, None)
            if val is None:
                return None
            self.data[key] = val
            return val
        else:
            val = self.children.pop(key, None)
            if val is None:
                return None

            # Add the value back to the top of the dict
            self.children[key] = val
            return val[keys]

    def set(self, keys: list | tuple, value: Value) -> int:
        """Set a value at the specified key path.

        Args:
            keys: Path through nested levels (length must match depth).
            value: Value to store.
        Returns:
            Number of new items added (0 if key existed, 1 if new).
        Raises:
            ValueError: If keys length doesn't match cache depth.
        """
        if len(keys) != self.depth:
            raise ValueError('Keys must match the depth of the cache')

        key, *keys = keys
        if self.depth == 1:
            ret = 1 if key not in self.data else 0
            self.data[key] = value
            self.size += ret
        else:
            if key not in self.children:
                self.children[key] = NestedCache(
                    signature=self.signature[1:],
                    max_size=self.max_size,
                    bucket_size=self.bucket_size,
                )
            ret = self.children[key].set(keys, value)
            self.size += ret

        if self.size > self.max_size:
            self.prune(self.bucket_size)
        return ret

    def __setitem__(self, keys: list | tuple, value: Value) -> None:
        self.set(keys, value)

    def delete(self, keys: list | tuple) -> int:
        """Delete a value at the specified key path.

        Args:
            keys: Path through nested levels (length must match depth).
        Returns:
            Number of items deleted (0 if not found, 1 if deleted).
        """
        if len(keys) != self.depth:
            return 0

        key, *keys = keys
        if self.depth == 1:
            if self.data.pop(key, _MISSING) is not _MISSING:
                self.size -= 1
                return 1
        else:
            if key in self.children:
                ret = self.children[key].delete(keys)
                if ret > 0:
                    if not self.children[key].size:
                        self.children.pop(key, None)
                    self.size -= ret
                    return ret
        return 0

    def __len__(self) -> int:
        return self.size

    def __contains__(self, keys: list | tuple) -> bool:
        return self[keys] is not None

    def __bool__(self) -> bool:
        return self.size > 0

    def __repr__(self) -> str:
        return f'NestedCache({self.signature}, size={self.size})'

    def __str__(self) -> str:
        return str(self.data)

    def items(self) -> Iterator[tuple[Keys, Value]]:
        """Iterator over all key-value pairs in the cache."""
        if self.depth == 1:
            for key, val in self.data.items():
                yield cast('Keys', (key,)), val
        else:
            for key, child in self.children.items():
                for keys, val in child.items():
                    yield cast('Keys', (key, *keys)), val

    def keys(self) -> Iterator[Keys]:
        """Iterator over all keys in the cache."""
        yield from (key for key, _ in self.items())

    def values(self) -> Iterator[Value]:
        """Iterator over all values in the cache."""
        yield from (val for _, val in self.items())

    def prune(self, n: int) -> int:
        """Remove approximately n items from the cache.

        For nested caches, distributes pruning proportionally across children
        based on their relative sizes.

        Args:
            n: Target number of items to remove.
        Returns:
            Actual number of items removed.
        """
        assert n > 0, 'Prune count must be positive'
        count = 0
        if self.depth == 1:
            # Snapshot keys before mutating (a live `dict.keys()` view raises if another thread
            # evicts mid-iteration) and pop with a sentinel so a key already removed by a
            # concurrent prune is skipped rather than raising -- lockless and crash-free.
            for key in list(self.data)[:n]:
                if self.data.pop(key, _MISSING) is not _MISSING:
                    count += 1
        else:
            for child in self.children.values():
                if not child:
                    continue
                target = math.ceil((child.size / self.size) * n)
                count += child.prune(target)
                if count >= n:
                    break

        self.size -= count
        return count
