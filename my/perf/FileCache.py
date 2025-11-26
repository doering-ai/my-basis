############
### HEAD ###
############
### STANDARD
from collections import deque, defaultdict

import regex as re
import functools as ft
from pathlib import Path
from typing import Iterator, ClassVar, Callable, TypeVar, Generic, Literal

### EXTERNAL
import pydantic as pyd
import logfire

### INTERNAL

############
### BODY ###
############
T = TypeVar('T')


class FileCache(Generic[T]):
    MAX_CACHE: ClassVar[int] = 2**16  # 64K
    NAME_RGX: ClassVar[re.Pattern] = re.compile(
        r'[\'"]?'.join([r'(?m)^', r'[[:lower:]][-_[:lower:]]++', r':(?:$| \{)'])
    )

    #      {group:   {prefix:  {file:    {name: item}}}}
    items: dict[str, dict[str, dict[str, dict[str, T]]]] = defaultdict(lambda: defaultdict(dict))

    #      {group:   {prefix:  {file:    { name }}}}
    files: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(lambda: defaultdict(dict))

    isize: int = 0
    fsize: int = 0
    max_size: int = MAX_CACHE

    directory: pyd.DirectoryPath
    writer: Callable[[str, dict[str, T]], None]
    reader: Callable[[str], dict[str, T]]
    splitter: Callable[[str], list[str]]

    # -------------------
    # `0` Initial Methods
    # -------------------
    def __init__(
        self,
        directory: pyd.DirectoryPath,
        writer: Callable[[str, dict[str, T]], None],
        reader: Callable[[str], dict[str, T]],
        splitter: Callable[[str], list[str]],
        max_size: int = 0,
    ) -> None:
        self.directory = directory
        self.writer = writer
        self.reader = reader
        self.splitter = splitter

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
        """
        Writes data to disk, removing it from the cache if present.
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
    # `x` Public Methods
    # ------------------
    def read(self, group: str, name: str) -> T | None:
        filename = self.splitter(name)[0]
        if (items := self.read_file(group, filename)) and name in items:
            return items[name]
        return None

    def write(self, group: str, name: str, item: T) -> None:
        filename = self.splitter(name)[0]
        if items := self.read_file(group, filename):
            items[name] = item
        else:
            self.write_file(group, filename, {name: item})

    def flush(self) -> None:
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
                if file_rgx.search(file) or any(map(name_rgx.search, items.keys())):
                    yield from items.values()

        elif mode == 'files' and group in self.files:
            if not prefix:
                file_iter = (fpair for fps in self.files[group].values() for fpair in fps.items())
            elif prefix in self.files[group]:
                file_iter = (fpair for fpair in self.files[group][prefix].items())
            else:
                return

            for file, names in file_iter:
                if file_rgx.search(file) or any(map(name_rgx.search, names)):
                    if file_items := self.read_file(group, file, prefix):
                        yield from file_items.values()
                    break
