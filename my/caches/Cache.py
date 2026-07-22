############
### HEAD ###
############
### STANDARD
from collections.abc import Hashable

### EXTERNAL
import pydantic as pyd

### INTERNAL


############
### BODY ###
############
class Cache[Key: Hashable, Value](pyd.BaseModel):
    """Simple LRU cache with automatic pruning when size limits are exceeded.

    Maintains insertion order with most recently accessed items at the end.
    When maxsize is reached, removes items in buckets from the front (oldest first).

    Examples:
        Fill a small cache, refresh one key, and watch the oldest bucket get pruned::

            >>> from my import Cache
            >>> cache = Cache[str, int](maxsize=4, bucket_size=2)
            >>> for i, key in enumerate('abcd'):
            ...     cache[key] = i
            >>> _ = cache['a']  # Refresh 'a', moving it to the back of the LRU order
            >>> cache['e'] = 4  # At maxsize: prunes one bucket ('b' and 'c') first
            >>> cache.keys()
            ['d', 'a', 'e']
    """

    #: The primary data of the cache, typed generically per instance.
    data: dict[Key, Value] = {}

    #: The maximum size of this cache, beyond which the oldest entries will be pruned.
    maxsize: int = pyd.Field(default=2**12, gt=0)  # 4096

    #: The amount of entries to prune at once (by default).
    bucket_size: int = pyd.Field(default=2**8, gt=0)  # 256

    def __getitem__(self, key: Key) -> Value | None:
        """Return the cached value (marking it most-recently-used), or None when absent."""
        if (ret := self.data.pop(key, None)) is not None:
            self.data[key] = ret  # move it to the bottom of the map
        return ret

    def __setitem__(self, key: Key, value: Value) -> None:
        """Store a value, first pruning a bucket of the oldest entries if the cache is full."""
        if key not in self.data and len(self.data) >= self.maxsize:
            self.prune(self.bucket_size)
        self.data[key] = value

    def __len__(self) -> int:
        return len(self.data)

    def __contains__(self, key: Key) -> bool:
        return key in self.data

    def items(self) -> list[tuple[Key, Value]]:
        """Return this cache's content as a list of key-value pairs."""
        return list(self.data.items())

    def keys(self) -> list[Key]:
        """Return this cache's keys as a list."""
        return list(self.data.keys())

    def values(self) -> list[Value]:
        """Return this cache's values as a list."""
        return list(self.data.values())

    def prune(self, n: int) -> None:
        """Remove the `n` oldest items from the cache (front of the insertion order).

        Snapshots the keys before mutating: a live `dict.keys()` view raises if another thread
        inserts or evicts mid-iteration, and a bare `del` raises if a key was already evicted by a
        concurrent prune. Iterating a list snapshot and using `pop(..., None)` makes pruning safe
        under concurrent access without a lock, since individual dict operations are atomic under
        the GIL.

        Args:
            n: The number of items to remove.
        Examples:
            Drop the two oldest entries::

                >>> from my import Cache
                >>> cache = Cache[str, int]()
                >>> for i, key in enumerate('abc'):
                ...     cache[key] = i
                >>> cache.prune(2)
                >>> cache.keys()
                ['c']
        """
        for key in list(self.data)[:n]:
            self.data.pop(key, None)
