############
### HEAD ###
############
# Standard imports
from typing import Any
from collections.abc import Hashable, Coroutine, Callable, Iterable
from datetime import datetime, timedelta
from pathlib import Path
import pickle as pkl
import tempfile
import os

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

    Examples:
        Persist data to disk, then read it back through a fresh instance::

            >>> import asyncio, tempfile
            >>> from my import PickleCache
            >>> tmp = tempfile.TemporaryDirectory()
            >>> cache = PickleCache(file=f'{tmp.name}/data.pkl', data={'a': 1})
            >>> cache['b'] = 2
            >>> cache.write()
            >>> fresh = PickleCache(file=f'{tmp.name}/data.pkl')
            >>> asyncio.run(fresh.read())
            {'a': 1, 'b': 2}
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
        Examples:
            Populate an empty cache from its async callback::

                >>> import asyncio, tempfile
                >>> from my import PickleCache
                >>> async def fetch():
                ...     return {'x': 10}
                >>> tmp = tempfile.TemporaryDirectory()
                >>> cache = PickleCache(file=f'{tmp.name}/cb.pkl', func=fetch)
                >>> asyncio.run(cache.read())
                {'x': 10}
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
        """Write current data to pickle file and update timestamps.

        Writes to a temporary file in the same directory and atomically renames it into
        place, so a crash or kill mid-write can never leave a torn/partially-written
        pickle file at `file`.

        Warning:
            This is a trust boundary -- only unpickle data you trust. `read()` calls
            `pickle.loads()` on whatever bytes are on disk at `file`, and unpickling
            arbitrary/untrusted data can execute arbitrary code. Treat this cache's file
            as trusted storage, not a format for exchanging data with other parties.
        """
        fd, tmp_name = tempfile.mkstemp(dir=self.file.parent, prefix=f'.{self.file.name}.')
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, 'wb') as ptr:
                pkl.dump(self.data, ptr)
            tmp_path.replace(self.file)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
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

    def get(self, key: Key, default: Any | None = None) -> Value | None:
        """Get value for key, returning default if not found."""
        return self.data.get(key, default)

    def items(self) -> Iterable[tuple[Key, Value]]:
        """Iterate through all key-value pairs in the cache."""
        return self.data.items()

    def keys(self) -> Iterable[Key]:
        """Iterate through all keys in the cache."""
        return self.data.keys()

    def values(self) -> Iterable[Value]:
        """Iterate through all values in the cache."""
        return self.data.values()
