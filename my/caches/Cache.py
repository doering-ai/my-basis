############
### HEAD ###
############
# Standard imports
from collections.abc import Hashable
import more_itertools as mi

# External imports
import pydantic as pyd

# Internal imports


############
### BODY ###
############
class Cache[Key: Hashable, Value](pyd.BaseModel):
    """Simple LRU cache with automatic pruning when size limits are exceeded.

    Maintains insertion order with most recently accessed items at the end.
    When maxsize is reached, removes items in buckets from the front (oldest first).
    """

    #: The primary data of the cache, typed generically per instance.
    data: dict[Key, Value] = {}

    #: The maximum size of this cache, beyond which the oldest entries will be pruned.
    maxsize: int = pyd.Field(default=2**12, gt=0)  # 4096

    #: The amount of entries to prune at once (by default).
    bucket_size: int = pyd.Field(default=2**8, gt=0)  # 256

    def __getitem__(self, key: Key) -> Value | None:
        if (ret := self.data.pop(key, None)) is not None:
            self.data[key] = ret  # move it to the bottom of the map
        return None

    def __setitem__(self, key: Key, value: Value) -> None:
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
        """Remove the `n` oldest items from the cache."""
        for key in mi.take(n, self.data.keys()):
            del self.data[key]
