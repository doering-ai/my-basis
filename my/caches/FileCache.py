############
### HEAD ###
############
### STANDARD
from collections import deque, defaultdict
from collections.abc import Iterator, Callable
from pathlib import Path
from typing import ClassVar, Literal
import functools as ft
import regex as re

### EXTERNAL
import pydantic as pyd
import logfire

### INTERNAL


############
### BODY ###
############
class FileCache[T]:
    """Two-level file-backed cache with in-memory LRU and on-disk persistence.

    Organizes items into a directory structure: group/prefix/filename where prefix
    is derived from filename. Maintains separate indices for in-memory (hot) items
    and on-disk (cold) files. Automatically prunes memory cache and writes to disk
    when size limits are exceeded.

    Structure:
    - items: In-memory cache of deserialized data
    - files: Index of on-disk files with their contained item names
    """

    MAX_CACHE: ClassVar[int] = 2**16  # 64K
    NAME_RGX: ClassVar[re.Pattern] = re.compile(
        r'[\'"]?'.join([r'(?m)^', r'[[:lower:]][-_[:lower:]]++', r':(?:$| \{)'])
    )

    #      {group:   {prefix:  {file:    {name: item}}}}
    items: dict[str, dict[str, dict[str, dict[str, T]]]]

    #      {group:   {prefix:  {file:    { name }}}}
    files: dict[str, dict[str, dict[str, set[str]]]]

    isize: int = 0
    fsize: int = 0
    max_size: int = MAX_CACHE

    directory: pyd.DirectoryPath
    writer: Callable[[str, dict[str, T]], None]
    reader: Callable[[str], dict[str, T]]
    splitter: Callable[[str], list[str]]

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(
        self,
        directory: pyd.DirectoryPath,
        writer: Callable[[str, dict[str, T]], None],
        reader: Callable[[str], dict[str, T]],
        splitter: Callable[[str], list[str]],
        max_size: int = 0,
    ) -> None:
        """Initialize a new FileCache."""
        self.directory = directory
        self.writer = writer
        self.reader = reader
        self.splitter = splitter
        self.items = defaultdict(lambda: defaultdict(dict))
        self.files = defaultdict(lambda: defaultdict(dict))

        assert self.directory and self.directory.is_dir(), 'Invalid cache directory.'
        for parent in filter(Path.is_dir, self.directory.iterdir()):
            group = parent.name
            for child in (d for d in parent.iterdir() if d.is_dir() and len(d.name) == 1):
                self._index_dir(group, child)

        if max_size:
            self.max_size = max_size

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    @ft.lru_cache(maxsize=16)
    def _prefix(filename: str) -> str:
        return re.sub(r'[-_]', '', filename[:6])[:3]

    def _index_dir(self, medium: str, cur: pyd.DirectoryPath) -> None:
        prefix = cur.name
        index = self.files[medium][prefix]
        for child in cur.iterdir():
            if child.is_dir():
                if len(prefix) < 3 and len(child.name) == 1:
                    self._index_dir(medium, child)
            else:
                index[child.stem] = set(self.NAME_RGX.findall(child.read_text()))

    def _get_item(self, group: str, prefix: str, filename: str) -> dict[str, T] | None:
        if (
            (group in self.items)
            and (prefix in self.items[group])
            and (filename in self.items[group][prefix])
        ):
            return self.items[group][prefix][filename]
        return None

    def _get_file(self, group: str, prefix: str, filename: str) -> set[str] | None:
        if (
            (group in self.files)
            and (prefix in self.files[group])
            and (filename in self.files[group][prefix])
        ):
            return self.files[group][prefix][filename]
        return None

    def _write(self, path: str, items: dict[str, T]) -> None:
        self.writer(path, dict(sorted(items.items())))

    # -------------------
    # `+` Primary Methods
    # -------------------
    def prune(self, n: int = 0):
        """Write oldest items to disk and remove from memory cache.

        Proportionally prunes from each group based on its size relative to total.
        Items are written to disk before removal from memory.

        Args:
            n: Number of items to prune (default: half of max_size).
        """
        # Setup buffers
        prefixes: deque[str] = deque()
        filenames: deque[str] = deque()
        n = n or self.max_size // 2

        # Remove a proportional amount from each group
        for group in self.items.keys():
            if not self.items[group]:
                continue

            count = 0
            size = sum(map(len, self.items[group].values()))
            target = round((size / self.isize) * n)

            piter = iter(self.items[group].keys())
            while count <= target and (prefix := next(piter, None)):
                fiter = iter(self.items[group][prefix].keys())
                while count <= target and (filename := next(fiter, None)):
                    items = self.items[group][prefix][filename]

                    path = '/'.join([group, *prefix, filename])
                    self.writer(path, items)

                    count += len(items)
                    filenames.append(filename)

                # Remove all the written items from the cache
                for filename in filenames:
                    self.items[group][prefix].pop(filename)
                filenames.clear()

                # Remember any prefixes that are now empty
                if not self.items[group][prefix]:
                    prefixes.append(prefix)

            for prefix in prefixes:
                self.items[group].pop(prefix)
            prefixes.clear()

            self.isize -= count

    def cache(self, group: str, filename: str, data: dict[str, T]) -> None:
        """Add or update items in the cache.

        Args:
            group: Category/namespace for the items.
            filename: File identifier (prefix derived automatically).
            data: Dictionary of items to cache.
        """
        prefix = self._prefix(filename)
        if indexed := self._get_item(group, prefix, filename):
            del self.items[group][prefix][filename]
            self.fsize -= len(indexed)
        elif i := self._get_item(group, prefix, filename):
            self.isize -= len(i)

        self.items[group][prefix][filename] = data
        self.isize += len(data)

        if self.isize >= self.max_size:
            self.prune()

    def read_file(self, group: str, filename: str, prefix: str = '') -> dict[str, T] | None:
        """Read all items from a file, loading from disk if needed.

        Args:
            group: Category/namespace.
            filename: File identifier.
            prefix: Optional prefix override (auto-derived if empty).
        Returns:
            Dictionary of items, or None if file doesn't exist.
        """
        prefix = prefix or self._prefix(filename)
        if items := self._get_item(group, prefix, filename):
            cache = self.items[group][prefix]
            items = cache.pop(filename)
            cache[filename] = items
            return items

        elif self._get_file(group, prefix, filename):
            path = '/'.join([group, *prefix, filename])
            data = self.reader(path)
            size = len(data)

            self.files[group][prefix].pop(filename)
            self.fsize -= size

            self.items[group][prefix][filename] = data
            self.isize += size

            return data

        return None

    def write_file(self, group: str, filename: str, data: dict[str, T]) -> None:
        """Write data directly to disk, merging with any cached data.

        Combines data with any existing cached items for this file before writing.
        Removes the file from memory cache and adds to disk index.

        Args:
            group: Category/namespace.
            filename: File identifier.
            data: Dictionary of items to write.
        """
        prefix = self._prefix(filename)
        if cached := self._get_item(group, prefix, filename):
            del self.items[group][prefix][filename]
            self.isize -= len(cached)
            data |= cached
        elif f := self._get_file(group, prefix, filename):
            self.fsize -= len(f)

        path = '/'.join([group, *prefix, filename])
        self.writer(path, data)

        self.files[group][prefix][filename] = {t[-1] for t in map(self.splitter, data.keys())}
        self.fsize += len(data)

    # ------------------
    # `*` Public Methods
    # ------------------
    def read(self, group: str, name: str) -> T | None:
        """Read a single item by name.

        Args:
            group: Category/namespace.
            name: Item identifier (filename derived via splitter).
        Returns:
            The item, or None if not found.
        """
        filename = self.splitter(name)[0]
        if (items := self.read_file(group, filename)) and name in items:
            return items[name]
        return None

    def write(self, group: str, name: str, item: T) -> None:
        """Write a single item, updating file on disk.

        Args:
            group: Category/namespace.
            name: Item identifier (filename derived via splitter).
            item: Item to store.
        """
        filename = self.splitter(name)[0]
        if items := self.read_file(group, filename):
            items[name] = item
        else:
            self.write_file(group, filename, {name: item})

    def flush(self) -> None:
        """Write all in-memory items to disk and clear memory cache."""
        for group in self.items.keys():
            for prefix in self.items[group].keys():
                for filename in self.items[group][prefix].keys():
                    self.writer(
                        '/'.join([group, *prefix, filename]),
                        self.items[group][prefix][filename],
                    )

        self.items.clear()
        self.fsize += self.isize
        self.isize = 0
        logfire.info(f'Flushed {self.fsize} items to disk')

    def search(
        self,
        group: str,
        file_rgx: re.Pattern,
        name_rgx: re.Pattern,
        prefix: str = '',
        mode: Literal['items', 'files', 'both'] = 'both',
    ) -> Iterator[T]:
        """Search for items by file or name patterns.

        Args:
            group: Category/namespace to search.
            file_rgx: Pattern to match against filenames.
            name_rgx: Pattern to match against item names.
            prefix: Optional prefix to limit search scope.
            mode: Search 'items' (memory), 'files' (disk), or 'both'.
        Yields:
            Items matching the search criteria.
        """
        if mode == 'both':
            yield from self.search(group, file_rgx, name_rgx, prefix, 'items')
            yield from self.search(group, file_rgx, name_rgx, prefix, 'files')

        elif mode == 'items' and group in self.items:
            if not prefix:
                item_iter = (ipair for ips in self.items[group].values() for ipair in ips.items())
            elif prefix in self.items[group]:
                item_iter = (ipair for ipair in self.items[group][prefix].items())
            else:
                return

            for file, items in item_iter:
                if file_rgx.search(file) or any(name_rgx.search(key) for key in items.keys()):
                    yield from items.values()

        elif mode == 'files' and group in self.files:
            if not prefix:
                file_iter = (fpair for fps in self.files[group].values() for fpair in fps.items())
            elif prefix in self.files[group]:
                file_iter = (fpair for fpair in self.files[group][prefix].items())
            else:
                return

            for file, names in file_iter:
                if file_rgx.search(file) or any(name_rgx.search(name) for name in names):
                    if file_items := self.read_file(group, file, prefix):
                        yield from file_items.values()
                    break
