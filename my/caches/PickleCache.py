############
### HEAD ###
############
# Standard imports
from collections.abc import Hashable, Coroutine, Callable, Iterable
from datetime import datetime, timedelta
from pathlib import Path
import pickle as pkl

# External imports
import pydantic as pyd

# Internal imports
from ..utils import ut


############
### BODY ###
############
class PickleCache[Key: Hashable, Value](pyd.BaseModel):
    """Persistent cache backed by pickle files with TTL-based invalidation.

    Supports three data sources with fallback hierarchy:
    1. In-memory data (fastest, if fresh)
    2. Pickle file on disk (if within TTL)
    3. Async callback function (if provided, refreshes cache)

    Data is automatically written to disk when refreshed from callback.
    """

    file: Path
    func: Callable[[], Coroutine[None, None, dict[Key, Value]]] | None = None
    data: dict[Key, Value] = {}
    ttl: timedelta = timedelta(days=1)

    last_read: datetime = pyd.Field(default_factory=lambda: ut.posix(0), exclude=True)
    last_write: datetime = pyd.Field(default_factory=lambda: ut.posix(0), exclude=True)

    @pyd.model_validator(mode='after')
    def _build(self) -> 'PickleCache':
        # I. Ensure the file path is absolute and exists
        self.file = self.file.expanduser().resolve()
        self.file.parent.mkdir(parents=True, exist_ok=True)

        # II. If the caller passed in data, immediately write it
        if self.data:
            self.write()

        return self

    async def read(self) -> dict[Key, Value]:
        """Refresh cache data, checking memory, disk, and callback in order.

        Falls back through data sources:
        1. Returns in-memory data if recent (within TTL)
        2. Loads from pickle file if it exists and is fresh
        3. Calls async func if provided and caches result

        Returns:
            Dictionary of cached data.
        """
        now = ut.posix()
        cutoff = now - self.ttl
        if self.last_read >= self.last_write > cutoff:
            # I. Read from memory
            pass

        elif self.file.exists() and (mtime := self.file.stat().st_mtime) > cutoff.timestamp():
            # II. Read from filesystem
            self.last_write = datetime.fromtimestamp(mtime)
            if self.last_write:
                self.data = pkl.loads(self.file.read_bytes())
                self.last_read = now
        elif self.func is not None:
            # III. Fetch anew and cache
            self.data = await self.func()
            self.write()

        return self.data

    def write(self) -> None:
        """Write current data to pickle file and update timestamps."""
        with open(self.file, 'wb') as ptr:
            pkl.dump(self.data, ptr)
        self.last_read = self.last_write = ut.posix()

    def __getitem__(self, key: Key) -> Value:
        return self.data[key]

    def __setitem__(self, key: Key, value: Value) -> None:
        self.data[key] = value

    def __delitem__(self, key: Key) -> None:
        if key in self.data:
            del self.data[key]

    def __len__(self) -> int:
        return len(self.data)

    def __contains__(self, key: Key) -> bool:
        return key in self.data

    def __ior__(self, other: dict[Key, Value]) -> 'PickleCache':
        """Merge another dictionary into this cache."""
        self.data.update(other)
        return self

    def get(self, key: Key, default: None) -> Value | None:
        """Get value for key, returning default if not found."""
        return self.data.get(key, default)

    def items(self) -> Iterable[tuple[Key, Value]]:
        """Iteratre through all key-value pairs in the cache."""
        return self.data.items()

    def keys(self) -> Iterable[Key]:
        """Iterate through all keys in the cache."""
        return self.data.keys()

    def values(self) -> Iterable[Value]:
        """Iterate through all values in the cache."""
        return self.data.values()
