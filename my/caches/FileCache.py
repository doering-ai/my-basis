############
### HEAD ###
############
### STANDARD
from collections import defaultdict
from collections.abc import Iterator, Callable
from pathlib import Path
from typing import ClassVar, Literal
import functools as ft
import regex as re

### EXTERNAL
import pydantic as pyd
import logfire
import srsly

### INTERNAL
from ..utils import ut

re.DEFAULT_VERSION = re.VERSION1

############
### DATA ###
############

type Reader[T] = Callable[[Path], T]
type Writer[T] = Callable[[Path, dict[str, T]], None]
type Splitter = Callable[[str], list[str]]


############
### BODY ###
############
class FileCache[T]:
    """Two-level file-backed cache with in-memory LRU and on-disk persistence.

    Organizes items into a directory structure: group/prefix/file where prefix
    is derived from file. Maintains separate indices for in-memory (hot) items
    and on-disk (cold) files. Automatically prunes memory cache and writes to disk
    when size limits are exceeded.

    Structure:
    - items: In-memory cache of deserialized data
    - files: Index of on-disk files with their contained item names
    """

    DEBUG: ClassVar[bool] = False
    MAX_CACHE: ClassVar[int] = 2**16  # 64K
    NAME_RGXS: ClassVar[dict[str, re.Pattern]] = ut.regex_dict(
        dict(
            yaml=r'(?m)^[\'"]?(\w.*?)[\'"]?:(?!\S)',
            json=r'(?m)^ {2,4}"(.+?)"\s*:(?!\S)',
        )
    )

    #      {group:   {prefix:  {file:    {name: item}}}}
    #: The in-memory cache of deserialized data.
    items: dict[str, dict[str, dict[str, dict[str, T]]]]

    #      {group:   {prefix:  {file:    { name }}}}
    #: The index of on-disk files and their contained item names.
    files: dict[str, dict[str, dict[str, set[str]]]]

    isize: int = 0  #: The current size of the in-memory cache.
    fsize: int = 0  #: The current size of the on-disk cache.
    max_size: int = MAX_CACHE  #: The maximum allowed size of the in-memory cache.
    filetype: str = '.json'  #: The default file extension for cached files.

    directory: pyd.DirectoryPath  #: The base directory for cache storage.
    writer: Writer  #: Function to write items to disk.
    reader: Reader  #: Function to read items from disk.
    splitter: Splitter  #: Function to split item names into components.

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(
        self,
        directory: pyd.DirectoryPath,
        writer: Writer | None = None,
        reader: Reader | None = None,
        splitter: Splitter | None = None,
        max_size: int = 0,
    ) -> None:
        """Initialize a new FileCache."""
        self.directory = directory
        self.writer = writer or self._default_writer
        self.reader = reader or self._default_reader
        self.splitter = splitter or self._default_splitter
        self.items = defaultdict(lambda: defaultdict(dict))
        self.files = defaultdict(lambda: defaultdict(dict))

        assert self.directory and self.directory.is_dir(), 'Invalid cache directory.'
        for parent in filter(Path.is_dir, self.directory.iterdir()):
            group = parent.name
            for child in parent.iterdir():
                if child.is_dir() and len(child.name) == 1:
                    self._index_dir(group, child, child.name)

        if max_size:
            self.max_size = max_size

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    @ft.lru_cache(maxsize=256)
    def _prefix(file: str) -> str:
        return re.sub(r'[_\W]', '', file[:6])[:3]

    def _index_dir(self, group: str, cur: pyd.DirectoryPath, prefix: str = '') -> None:
        for child in cur.iterdir():
            if child.is_dir():
                if len(prefix) < 3 and len(child.name) == 1:
                    self._index_dir(group, child, prefix + child.name)
            else:
                ftype = child.suffix[1:].lower()
                if ftype in {'yaml', 'yml', ''}:
                    rgx = 'yaml'
                elif ftype in {'json'}:
                    rgx = 'json'
                else:
                    raise ValueError(f'Unsupported file type: {ftype}')

                items = self.NAME_RGXS[rgx].findall(child.read_text())
                self.files[group][prefix][child.stem] = set(items)

    def _path(self, group: str, prefix: str, file: str) -> Path:
        """Generate the full path for a cached file."""
        return (self.directory / '/'.join([group, *prefix, file])).with_suffix(self.filetype)

    def _get_mem_items(self, group: str, prefix: str, file: str) -> dict[str, T] | None:
        if (
            (group in self.items)
            and (prefix in self.items[group])
            and (file in self.items[group][prefix])
        ):
            return self.items[group][prefix][file]
        return None

    def _get_sys_items(self, group: str, prefix: str, file: str) -> set[str] | None:
        if (
            (group in self.files)
            and (prefix in self.files[group])
            and (file in self.files[group][prefix])
        ):
            return self.files[group][prefix][file]
        return None

    def _write(self, path: Path, items: dict[str, T]) -> None:
        self.writer(path, dict(sorted(items.items())))

    def _default_writer(self, path: Path, items: dict[str, T]) -> None:
        """Default writer using JSON format."""
        path.parent.mkdir(parents=True, exist_ok=True)
        srsly.write_json(path, items, indent=4)

    def _default_reader(self, path: Path) -> dict[str, T]:
        """Default reader using JSON format."""
        if path.exists():
            ret = srsly.read_json(path)
            assert isinstance(ret, dict)
            return ret
        return {}

    def _default_splitter(self, stem: str) -> list[str]:
        return re.split(r'[_\W]+', stem)

    def _prune_group(self, group: str, n: int):
        if not self.items[group]:
            return

        count = 0
        size = self.group_isize(group)
        target = round((size / self.isize) * n)

        # Iterate through prefixes
        for prefix in list(self.items[group].keys()):
            # Iterate through filestems
            for file in list(self.items[group][prefix].keys()):
                names = self.move_to_sys(group, file, prefix=prefix)
                count += len(names)
                if count >= target:
                    return

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
        n = n or (self.max_size // 2)

        # Remove a proportional amount from each group
        for group in self.items.keys():
            self._prune_group(group, n)

    def group_isize(self, group: str) -> int:
        """Get the number of items currently cached in memory for a group."""
        return sum(len(items) for pre in self.items[group].values() for items in pre.values())

    def group_fsize(self, group: str) -> int:
        """Get the number of items currently cached on disk for a group."""
        return sum(len(names) for pre in self.files[group].values() for names in pre.values())

    def read_from_cache(self, group: str, file: str, prefix: str = '') -> dict[str, T] | None:
        """Read all items from a file, loading from disk if needed.

        Args:
            group: Category/namespace.
            file: File identifier.
            prefix: Optional prefix override (auto-derived if empty).
        Returns:
            Dictionary of items, or None if file doesn't exist.
        """
        prefix = prefix or self._prefix(file)
        if items := self._get_mem_items(group, prefix, file):
            cache = self.items[group][prefix]
            cache[file] = cache.pop(file)
            return items

        elif self._get_sys_items(group, prefix, file):
            return self.move_to_mem(group, file, prefix=prefix)

        return None

    def write_to_cache(
        self,
        group: str,
        file: str,
        data: dict[str, T],
        overwrite: bool = True,
    ) -> None:
        """Add or replace items in the cache.

        Args:
            group: Category/namespace for the items.
            file: File identifier (prefix derived automatically).
            data: Dictionary of items to cache.
            overwrite: Whether to overwrite existing items, or add to them.
        """
        prefix = self._prefix(file)
        if item := self.read_from_cache(group, file, prefix):
            self.isize -= len(item)
            if not overwrite:
                data = item | data

        self.items[group][prefix][file] = data
        self.isize += len(data)
        if self.isize >= self.max_size:
            self.prune()

    def move_to_sys(self, group: str, file: str, prefix: str = '') -> set[str]:
        """Write a file's items directly to disk, overwriting any existing data.

        Combines data with any existing cached items for this file before writing.
        Removes the file from memory cache and adds to disk index.

        Args:
            group: Category/namespace.
            file: File identifier.
            prefix: Optional prefix override (auto-derived if empty).
        Returns:
            The number of items written.
        """
        prefix = prefix or self._prefix(file)
        path = self._path(group, prefix, file)
        if self.DEBUG:
            assert not self._get_sys_items(group, prefix, file), f'Stored file AND item for {file}.'

        data = self._get_mem_items(group, prefix, file)
        assert data, 'No cached items to write to file.'

        del self.items[group][prefix][file]
        self.isize -= (n := len(data))

        # Delete empty prefixes
        if not self.items[group][prefix]:
            del self.items[group][prefix]

        self._write(path, data)
        self.files[group][prefix][file] = ret = set(data.keys())
        self.fsize += n
        return ret

    def move_to_mem(self, group: str, file: str, prefix: str = '') -> dict[str, T]:
        """Load a file's items from disk into memory cache."""
        prefix = prefix or self._prefix(file)
        path = self._path(group, prefix, file)
        if self.DEBUG:
            assert not self._get_mem_items(group, prefix, file), f'Stored file AND item for {file}.'

        assert path.exists(), f'Indexed file missing on disk: {path}'
        data = self.reader(path)
        size = len(data)

        del self.files[group][prefix][file]
        self.fsize -= size

        # Delete empty prefixes
        if not self.files[group][prefix]:
            del self.files[group][prefix]

        self.items[group][prefix][file] = data
        self.isize += size

        return data

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    def __getitem__(self, data: tuple[str, str]) -> T | None:
        """Get an item by group and name.

        Args:
            data: Tuple of (group, name).
        Returns:
            The item, or None if not found.
        """
        group, name = data
        return self.read(group, name)

    def __setitem__(self, data: tuple[str, str], item: T) -> None:
        """Set an item by group and name.

        Args:
            data: Tuple of (group, name).
            item: Item to store.
        """
        group, name = data
        self.write(group, name, item)

    def __len__(self) -> int:
        """Get the total number of items in memory and on disk."""
        return self.isize + self.fsize

    # -------------------
    # `*1` Main Interface
    # -------------------
    def read(self, group: str, name: str) -> T | None:
        """Read a single item by name into memory if it exists, else return None.

        Args:
            group: Category/namespace.
            name: Item identifier (file derived via splitter).
        Returns:
            The item, or None if not found.
        """
        file = self.splitter(name)[0]
        if (items := self.read_from_cache(group, file)) and name in items:
            return items[name]
        return None

    def write(self, group: str, name: str, item: T) -> None:
        """Write a single item set the value of an item by name (in memory, for now).

        Args:
            group: Category/namespace.
            name: Item identifier (file derived via splitter).
            item: Item to store.
        """
        file = self.splitter(name)[0]
        if items := self.read_from_cache(group, file):
            if name not in items:
                self.isize += 1
            items[name] = item
        else:
            self.write_to_cache(group, file, {name: item})

    def flush(self) -> None:
        """Write all in-memory items to disk and clear memory cache."""
        for group in self.items.keys():
            for prefix in self.items[group].keys():
                for file in self.items[group][prefix].keys():
                    self._write(
                        self._path(group, prefix, file),
                        self.items[group][prefix][file],
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
                    if file_items := self.read_from_cache(group, file, prefix):
                        yield from file_items.values()
                    break
