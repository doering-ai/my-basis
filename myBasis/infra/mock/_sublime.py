"""Runtime mock for the `sublime` C-extension module.

Injected into sys.modules['sublime'] by PyTest.mock.install() so that
plugin code can be imported and exercised outside a live SublimeText process.

Implements:
  - Region, Selection, Edit, Settings, View, Window  (with real in-memory behaviour)
  - Module-level stubs: version, platform, packages_path, cache_path,
    installed_packages_path, load_settings, set_timeout, set_timeout_async,
    load_resource, encode_value, decode_value, active_window

Everything else (Sheet, Buffer, syntax queries, …) is left as a MagicMock so
that imports succeed and attribute access doesn't crash; only call-sites that
actually assert on the return value will need explicit stub additions.
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any, Callable, Iterator, Literal, ClassVar
from pathlib import Path
from unittest.mock import MagicMock
import functools as ft
import itertools as it
import json
import os
import sys

### EXTERNAL
import pydantic as pyd

### INTERNAL
from .Buffer import Buffer


############
### DATA ###
############
VER_STR = f'python{sys.version_info.major}{sys.version_info.minor}'
MODE = 'external'


Directory = pyd.DirectoryPath


class MockedPathCache(pyd.BaseModel):
    @ft.cached_property
    def main(self) -> Directory:
        path = Path(os.getenv('ST_MAIN', '')).expanduser().resolve()
        if not (path and path.exists()):
            xdg = Path(os.getenv('XDG_CONFIG_HOME', '~/.config')).expanduser().resolve()
            path = xdg / 'sublime-text'

        if not (path and path.exists() and path.is_dir()):
            raise ValueError('Could not infer $ST_MAIN -- please set manually.')
        return path

    @ft.cached_property
    def cache(self) -> Directory:
        path = Path(os.getenv('ST_CACHE', '')).expanduser().resolve()
        if not (path and path.exists()):
            xdg = Path(os.getenv('XDG_CACHE_HOME', '~/.cache')).expanduser().resolve()
            path = xdg / 'sublime_text'

        if not (path and path.exists() and path.is_dir()):
            raise ValueError('Could not infer $ST_CACHE -- please set manually.')
        return path

    @ft.cached_property
    def root(self) -> Directory:
        path = Path(os.getenv('ST_ROOT', '/opt/sublime_text')).expanduser().resolve()
        if not path and path.exists() and path.is_dir():
            raise ValueError('Could not infer $ST_ROOT -- please set manually.')
        return path


PATHS = MockedPathCache()


############
### BODY ###
############
class Edit:
    """An unvalidated edit token mock."""

    def __init__(self, token: int = 0) -> None:
        self.edit_token = token

    def __repr__(self) -> str:
        return f'Edit({self.edit_token})'


class Region:
    """Re-implementation of sublime.Region with full arithmetic."""

    def __init__(self, a: int, b: int | None = None, xpos: float = -1.0) -> None:
        self.a = a
        self.b = a if b is None else b
        self.xpos = xpos

    # ----------
    # Positional
    # ----------
    def begin(self) -> int:
        return min(self.a, self.b)

    def end(self) -> int:
        return max(self.a, self.b)

    def size(self) -> int:
        return abs(self.b - self.a)

    def empty(self) -> bool:
        return self.a == self.b

    def to_tuple(self) -> tuple:
        return (self.a, self.b)

    # --------------
    # Set Operations
    # --------------
    def contains(self, x: 'Region | int') -> bool:
        if isinstance(x, Region):
            return self.begin() <= x.begin() and x.end() <= self.end()
        return self.begin() <= x <= self.end()

    def cover(self, rhs: 'Region') -> 'Region':
        return Region(min(self.begin(), rhs.begin()), max(self.end(), rhs.end()))

    def intersection(self, rhs: 'Region') -> 'Region':
        a = max(self.begin(), rhs.begin())
        b = min(self.end(), rhs.end())
        return Region(a, max(a, b))

    def intersects(self, rhs: 'Region') -> bool:
        return self.begin() < rhs.end() and rhs.begin() < self.end()

    # -------------
    # Magic Methods
    # -------------
    def __len__(self) -> int:
        return self.size()

    def __bool__(self) -> bool:
        return True  # a Region always exists; emptiness ≠ falsiness in ST

    def __eq__(self, rhs: object) -> bool:
        if not isinstance(rhs, Region):
            return NotImplemented
        return self.a == rhs.a and self.b == rhs.b

    def __lt__(self, rhs: object) -> bool:
        if not isinstance(rhs, Region):
            return NotImplemented
        return (self.begin(), self.end()) < (rhs.begin(), rhs.end())

    def __contains__(self, v: 'Region | int') -> bool:
        return self.contains(v)

    def __repr__(self) -> str:
        return f'Region({self.a}, {self.b})'


class Selection:
    """Ordered, non-overlapping list of Regions (simplified — no merging)."""

    def __init__(self, view_id: int = 0) -> None:
        self.view_id = view_id
        self._regions: list = []

    def is_valid(self) -> bool:
        return True

    def clear(self) -> None:
        self._regions.clear()

    def add(self, x: 'Region | int') -> None:
        region = Region(x, x) if isinstance(x, int) else x
        self._regions.append(region)
        self._regions.sort(key=lambda r: r.begin())

    def add_all(self, regions: 'Any') -> None:
        for r in regions:
            self.add(r)

    def subtract(self, region: 'Region') -> None:
        self._regions = [r for r in self._regions if r != region]

    def contains(self, region: 'Region') -> bool:
        return any(r.contains(region) for r in self._regions)

    # -------------
    # Magic Methods
    # -------------
    def __iter__(self) -> 'Iterator[Region]':
        return iter(self._regions)

    def __reversed__(self) -> 'Iterator[Region]':
        return reversed(self._regions)

    def __len__(self) -> int:
        return len(self._regions)

    def __getitem__(self, index: int) -> 'Region':
        return self._regions[index]

    def __delitem__(self, index: int) -> None:
        del self._regions[index]

    def __eq__(self, rhs: object) -> bool:
        if isinstance(rhs, Selection):
            return self._regions == rhs._regions
        return NotImplemented

    def __bool__(self) -> bool:
        return bool(self._regions)

    def __repr__(self) -> str:
        return f'Selection({self._regions!r})'


class Settings:
    """Dict-backed settings object."""

    _ID_COUNTER: ClassVar[Iterator[int]] = it.count(1)

    settings_id: int
    _data: dict

    def __init__(self, id: int | None = None) -> None:  # noqa
        self.settings_id = id if id is not None else next(self._ID_COUNTER)
        self._data = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def has(self, key: str) -> bool:
        return key in self._data

    def erase(self, key: str) -> None:
        self._data.pop(key, None)

    def setdefault(self, key: str, value: Any) -> Any:
        return self._data.setdefault(key, value)

    def update(self, other: Any = None, /, **kwargs: Any) -> None:
        if other:
            self._data.update(other)
        self._data.update(kwargs)

    def to_dict(self) -> dict:
        return dict(self._data)

    def add_on_change(self, tag: str, callback: 'Callable[[], None]') -> None:
        pass

    def clear_on_change(self, tag: str) -> None:
        pass

    # -------------
    # Magic Methods
    # -------------
    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f'Settings({self._data!r})'


_GLOBAL_SETTINGS = Settings()

#: A map of command names to `callable(view, args)` functions; extend as needed.
MOCK_COMMANDS: dict = {}


class View:
    """Mock view backed by a Buffer.

    Supports the API subset used by ViewTestCase and Utils.batch_write.
    run_command handles the three commands required by ViewTestCaseMixin:
    'insert', 'select_all', 'right_delete'.

    Unknown commands are silently ignored (override _dispatch_command to extend).
    """

    view_id: int
    selection: Selection
    settings_object: Settings | None

    _ID_COUNTER: ClassVar[Iterator[int]] = it.count(1)

    def __init__(self, id: int | None = None, window: 'Window | None' = None) -> None:  # noqa: A002
        self.view_id = id if id is not None else next(self._ID_COUNTER)
        self._buf = Buffer()
        self.selection = Selection(self.view_id)
        self.selection.add(Region(0, 0))  # start with a cursor at 0
        self.settings_object = _GLOBAL_SETTINGS
        self._scratch = False
        self._read_only = False
        self._window = window

    # --------
    # Identity
    # --------
    def id(self) -> int:
        return self.view_id

    def is_valid(self) -> bool:
        return True

    def is_loading(self) -> bool:
        return False

    def is_dirty(self) -> bool:
        return False

    def is_read_only(self) -> bool:
        return self._read_only

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = read_only

    def is_scratch(self) -> bool:
        return self._scratch

    def set_scratch(self, scratch: bool) -> None:
        self._scratch = scratch

    def file_name(self) -> 'str | None':
        return None

    def close(self) -> None:
        pass

    def window(self) -> 'Window | None':
        return self._window

    # -------------
    # Buffer access
    # -------------
    def size(self) -> int:
        return self._buf.size()

    def substr(self, x: 'Region | int') -> str:
        if isinstance(x, Region):
            return self._buf.substr(x.begin(), x.end())
        return self._buf.substr(x, x + 1)

    def insert(self, edit: Edit, point: int, text: str) -> int:
        return self._buf.insert(point, text)

    def replace(self, edit: Edit, region: Region, text: str) -> None:
        self._buf.replace(region.begin(), region.end(), text)

    def erase(self, edit: Edit, region: Region) -> None:
        self._buf.replace(region.begin(), region.end(), '')

    # ------------------
    # Coordinate queries
    # ------------------
    def text_point(self, row: int, col: int) -> int:
        return self._buf.text_point(row, col)

    def rowcol(self, point: int) -> tuple:
        return self._buf.rowcol(point)

    def line(self, x: 'Region | int') -> Region:
        if isinstance(x, Region):
            a, _ = self._buf.line_extent(x.begin())
            _, b = self._buf.line_extent(x.end())
        else:
            a, b = self._buf.line_extent(x)
        return Region(a, b)

    # ---------
    # Selection
    # ---------
    def sel(self) -> Selection:
        return self.selection

    # --------
    # Settings
    # --------
    def settings(self) -> Settings:
        return self.settings_object or _GLOBAL_SETTINGS

    def assign_syntax(self, syntax: str) -> None:
        pass

    # --------
    # Commands
    # --------
    def run_command(self, name: str, args: 'dict | None' = None) -> None:
        args = args or {}

        if command := MOCK_COMMANDS.get(name):
            command(self, args)
            return

        if name == 'insert':
            self._cmd_insert(args.get('characters', ''))
        elif name == 'select_all':
            self._cmd_select_all()
        elif name == 'right_delete':
            self._cmd_right_delete()
        elif name == 'append':
            self._buf.insert(self._buf.size(), args.get('characters', ''))
        # Unknown commands are silently ignored.

    def _cmd_insert(self, chars: str) -> None:
        sel = sorted(self.selection, key=lambda r: r.begin(), reverse=True)
        new_cursors = []
        for region in sel:
            a, b = region.begin(), region.end()
            self._buf.replace(a, b, chars)
            new_cursors.insert(0, a + len(chars))
        self.selection.clear()
        for cursor in new_cursors:
            self.selection.add(Region(cursor, cursor))

    def _cmd_select_all(self) -> None:
        self.selection.clear()
        self.selection.add(Region(0, self._buf.size()))

    def _cmd_right_delete(self) -> None:
        sel = sorted(self.selection, key=lambda r: r.begin(), reverse=True)
        min_pos = None
        for region in sel:
            a, b = region.begin(), region.end()
            if a == b:
                b = min(b + 1, self._buf.size())
            self._buf.replace(a, b, '')
            if min_pos is None or a < min_pos:
                min_pos = a
        self.selection.clear()
        self.selection.add(Region(min_pos or 0, min_pos or 0))

    # -------------
    # Magic Methods
    # -------------
    def __bool__(self) -> bool:
        return True

    def __len__(self) -> int:
        return self._buf.size()

    def __hash__(self) -> int:
        return self.view_id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, View) and self.view_id == other.view_id

    def __repr__(self) -> str:
        return f'View({self.view_id})'


class Window:
    _ID_COUNTER: ClassVar[Iterator[int]] = it.count(1)

    def __init__(self, id: int | None = None) -> None:  # noqa: A002
        self.window_id = id if id is not None else next(self._ID_COUNTER)
        self._views: list = []
        self._active_view: 'View | None' = None
        self._settings = Settings()

    def id(self) -> int:
        return self.window_id

    def is_valid(self) -> bool:
        return True

    def active_view(self) -> 'View | None':
        return self._active_view

    def new_file(self, flags: int = 0, syntax: str = '') -> View:
        view = View(window=self)
        self._views.append(view)
        self._active_view = view
        return view

    def views(self, *, include_transient: bool = False) -> list:
        return list(self._views)

    def settings(self) -> Settings:
        return self._settings

    def run_command(self, cmd: str, args: 'dict | None' = None) -> None:
        pass  # no-op for window-level commands in tests

    def show_input_panel(
        self, caption: str, initial_text: str, on_done: Any, on_change: Any, on_cancel: Any
    ) -> View:
        return self.new_file()

    def create_output_panel(self, name: str) -> View:
        return self.new_file()

    def show_panel(self, panel: str, **kwargs: Any) -> None:
        pass

    def folders(self) -> list:
        return []

    # -------------
    # Magic Methods
    # -------------
    def __bool__(self) -> bool:
        return True

    def __hash__(self) -> int:
        return self.window_id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Window) and self.window_id == other.window_id

    def __repr__(self) -> str:
        return f'Window({self.window_id})'


_GLOBAL_WINDOW = Window()


############
### MAIN ###
############
def active_window() -> Window:
    return _GLOBAL_WINDOW


def version() -> str:
    return '4200'


def platform() -> Literal['osx', 'linux', 'windows']:
    if sys.platform == 'darwin':
        return 'osx'
    if sys.platform == 'win32':
        return 'windows'
    return 'linux'


def packages_path() -> str:
    return str(PATHS.main / 'Packages')


def installed_packages_path() -> str:
    return str(PATHS.main / 'Installed Packages')


def cache_path() -> str:
    return str(PATHS.cache)


def executable_path() -> str:
    return str(PATHS.root / 'sublime_text')


def load_settings(base_name: str) -> Settings:
    return _GLOBAL_SETTINGS


def save_settings(base_name: str) -> None:
    pass


def encode_value(val: Any, pretty: bool = False, update_text: str = '') -> str:
    return json.dumps(val, indent=4 if pretty else None)


def decode_value(data: str) -> Any:
    return json.loads(data)


def load_resource(name: str) -> str:
    """Attempt to read from disk; raise FileNotFoundError if not found."""
    # Strip leading "Packages/" and try to resolve relative to packages_path()
    stripped = name.removeprefix('Packages/')
    candidate = Path(packages_path()) / stripped
    if candidate.exists():
        return candidate.read_text(encoding='utf-8')
    raise FileNotFoundError(f'Resource not found (offline mock): {name!r}')


def set_timeout(callback: 'Callable[[], Any]', delay: int = 0) -> None:
    """Run immediately — no real event loop in offline tests."""
    callback()


def set_timeout_async(callback: 'Callable[[], Any]', delay: int = 0) -> None:
    """Run immediately — no real event loop in offline tests."""
    callback()


# Catch-all: any attribute not defined above returns a MagicMock so that
# imports of exotic ST APIs don't immediately crash.
_KNOWN_MOCKS = {}


def __getattr__(name: str) -> Any:
    return _KNOWN_MOCKS.setdefault(name, MagicMock(name=f'sublime.{name}'))
