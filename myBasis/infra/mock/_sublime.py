"""Runtime mock for the `sublime` C-extension module.

Injected into sys.modules['sublime'] by PyTest.mock.install() so that
plugin code can be imported and exercised outside a live SublimeText process.

Implements:
  - Region, Selection, Edit, Settings, View, Window  (with real in-memory behaviour)
  - Module-level stubs: version, platform, packages_path, cache_path,
    installed_packages_path, load_settings, set_timeout, set_timeout_async,
    load_resource, encode_value, decode_value, active_window

Everything else (e.g. syntax queries) is left as a MagicMock so
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
from dataclasses import dataclass
import functools as ft
import itertools as it
import json
import os
import sys

### EXTERNAL
import pydantic as pyd

### INTERNAL
from .Buffer import Buffer
from ._sublime_enums import *  # noqa: F403

# ruff: noqa: F405, A002


############
### DATA ###
############
VER_STR = f'python{sys.version_info.major}{sys.version_info.minor}'
MODE = 'external'


Directory = pyd.DirectoryPath


def infer_paths() -> tuple[Directory, Directory, Directory]:
    def home() -> Directory:
        path = None
        if envvar := os.getenv('ST_HOME'):
            path = Path(envvar).expanduser().resolve()
        elif envvar := os.getenv('ST_PKGS'):
            path = Path(envvar).expanduser().resolve().parent

        if not (path and path.exists()):
            xdg = Path(os.getenv('XDG_CONFIG_HOME', '~/.config')).expanduser().resolve()
            path = xdg / 'sublime-text'

        if not (path and path.exists() and path.is_dir()):
            raise ValueError('Could not infer $ST_MAIN -- please set manually.')
        return path

    def cache() -> Directory:
        path = None
        if envvar := os.getenv('ST_CACHE'):
            path = Path(envvar).expanduser().resolve()

        if not (path and path.exists()):
            xdg = Path(os.getenv('XDG_CACHE_HOME', '~/.cache')).expanduser().resolve()
            path = xdg / 'sublime-text' / 'Cache'

        if not (path and path.exists() and path.is_dir()):
            raise ValueError('Could not infer $ST_CACHE -- please set manually.')
        return path

    def root() -> Directory:
        path = Path(os.getenv('ST_ROOT', '/opt/sublime_text')).expanduser().resolve()
        if not path and path.exists() and path.is_dir():
            raise ValueError('Could not infer $ST_ROOT -- please set manually.')
        return path

    return home(), cache(), root()


ST_HOME, ST_CACHE, ST_ROOT = infer_paths()


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


@dataclass
class HistoricPosition:
    """Provides a snapshot of the row and column info for a `Point`, before `View` changes.

    This is primarily useful for replaying changes to a document.
    """

    pt: int
    """The offset from the beginning of the `View`."""
    row: int
    """The row the `pt` was in when the `HistoricPosition` was recorded."""
    col: int
    """The column the `py` was in when the `HistoricPosition` was recorded in Unicode characters."""
    col_utf16: int
    """The value of `col`, but in UTF-16 code units."""
    col_utf8: int
    """The value of `col`, but in UTF-8 code units."""


@dataclass
class TextChange:
    """Represents a change that occurred to the text of a `View`.

    This is primarily useful for replaying changes to a document.
    """

    a: HistoricPosition
    """The beginning `HistoricPosition` of the region that was modified."""
    b: HistoricPosition
    """The ending `HistoricPosition` of the region that was modified."""
    len_utf16: int
    """The length of the old contents, in UTF-16 code units."""
    len_utf8: int
    """The length of the old contents, in UTF-8 code units."""
    str: str
    """A string of the new contents of the region specified by `a` and `b`."""

    def __init__(
        self, pa: HistoricPosition, pb: HistoricPosition, len_utf16: int, len_utf8: int, s: str
    ) -> None:
        self.a = pa
        self.b = pb
        self.len_utf16 = len_utf16
        self.len_utf8 = len_utf8
        self.str = s


class Selection:
    """Ordered, non-overlapping list of Regions (simplified — no merging)."""

    view_id: int
    _regions: list[Region]

    def __init__(self, view_id: int = 0) -> None:
        self.view_id = view_id
        self._regions = []

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
        if region in self._regions:
            self._regions.remove(region)

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
    _callbacks: dict[str, Callable[[], None]]

    def __init__(self, id: int | None = None) -> None:
        self.settings_id = id if id is not None else next(self._ID_COUNTER)
        self._data = {}
        self._callbacks = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._notify()

    def has(self, key: str) -> bool:
        return key in self._data

    def erase(self, key: str) -> None:
        self._data.pop(key, None)
        self._notify()

    def setdefault(self, key: str, value: Any) -> Any:
        ret = self._data.setdefault(key, value)
        self._notify()
        return ret

    def update(self, other: Any = None, /, **kwargs: Any) -> None:
        if other:
            self._data.update(other)
        self._data.update(kwargs)
        self._notify()

    def to_dict(self) -> dict:
        return dict(self._data)

    def add_on_change(self, tag: str, callback: Callable[[], None]) -> None:
        self._callbacks[tag] = callback

    def clear_on_change(self, tag: str) -> None:
        self._callbacks.pop(tag, None)

    def _notify(self) -> None:
        for callback in self._callbacks.values():
            callback()

    # -------------
    # Magic Methods
    # -------------
    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._notify()

    def __delitem__(self, key: str) -> None:
        del self._data[key]
        self._notify()

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

    def __init__(self, id: int | None = None, window: 'Window | None' = None) -> None:
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


@dataclass
class Html:
    """Used to indicate that a string is formatted as HTML."""

    data: str = ''


class Sheet:
    """Represents a content container, i.e. a tab, within a window.

    Sheets may contain a `View`, or an image preview.
    """

    sheet_id: int
    _view: View | None

    def __init__(self, id: int) -> None:
        self.sheet_id = id
        self._view = None

    def __hash__(self) -> int:
        return self.sheet_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Sheet):
            return False
        else:
            return self.sheet_id == other.sheet_id

    def __repr__(self) -> str:
        return f'Sheet({self.sheet_id})'

    def id(self) -> int:
        """A number that uniquely identifies this sheet."""
        return self.sheet_id

    def window(self) -> Window | None:
        """The `Window` containing this sheet. May be `None` if the sheet has been closed."""
        return _GLOBAL_WINDOW

    def view(self) -> View | None:
        """The `View` contained within the sheet if any."""
        return self._view

    def file_name(self) -> str | None:
        """The full name of the file associated with the sheet, or `None` if it doesn't exist."""
        return None

    def is_semi_transient(self) -> bool:
        """Whether this sheet is semi-transient."""
        return False

    def is_transient(self) -> bool:
        """Whether this sheet is exclusively transient.

        Note that a sheet may be both open as a regular file and be transient.
        In this case `is_transient` will still return `False`.
        """
        return False

    def is_selected(self) -> bool:
        """Whether this sheet is currently selected."""
        return True

    def group(self) -> int | None:
        """The (layout) group that the sheet is contained within."""

    def close(self, on_close: Callable[[bool], None] | None = None) -> None:
        """Closes the sheet."""
        if on_close:
            on_close(True)


class TextSheet(Sheet):
    """Specialization for sheets containing editable text, ie. a `View`."""

    _name: str

    def __repr__(self) -> str:
        return f'TextSheet({self.sheet_id})'

    def set_name(self, name: str) -> None:
        """Set the name displayed in the tab. Only affects unsaved files."""
        self._name = name


class ImageSheet(Sheet):
    """Specialization for sheets containing an image."""

    def __repr__(self) -> str:
        return f'ImageSheet({self.sheet_id})'


class HtmlSheet(Sheet):
    """Specialization for sheets containing HTML."""

    _name: str = ''
    _text: str = ''

    def __repr__(self) -> str:
        return f'HtmlSheet({self.sheet_id})'

    def set_name(self, name: str) -> None:
        """Set the name displayed in the tab."""
        self._name = name

    def set_contents(self, contents: str) -> None:
        """Set the HTML content of the sheet."""
        self._text = contents


class CompletionList:
    """Represents a list of completions, some of which may be in the process of being fetched."""

    target: Any | None = None
    completions: list[str] | list[tuple[str, str]] | list[CompletionItem] | None = None
    flags: AutoCompleteFlags = AutoCompleteFlags.NONE

    def __init__(
        self,
        completions: list[str] | list[tuple[str, str]] | list[CompletionItem] | None = None,
        flags: AutoCompleteFlags = AutoCompleteFlags.NONE,
    ) -> None:
        """Initialize the list.

        - `completions` - If `None` is passed, the method `set_completions()` must be called before
          the completions will be displayed to the user.
        - `flags` - Flags controlling auto-complete behavior.
        """
        self.target = None
        self.completions = completions
        self.flags = flags

    def __repr__(self) -> str:
        return f'CompletionList(completions={self.completions!r}, flags={self.flags!r})'

    def set_completions(
        self,
        completions: list[str] | list[tuple[str, str]] | list[CompletionItem],
        flags: AutoCompleteFlags = AutoCompleteFlags.NONE,
    ) -> None:
        """Sets the list of completions, allowing the list to be displayed to the user."""
        self.completions = completions
        if flags.value:
            self.flags = flags


@dataclass
class CompletionItem:
    """Represents an available auto-completion item."""

    trigger: str = ''
    """Text to match against the user's input."""
    annotation: str = ''
    """A hint to draw to the right-hand side of the trigger."""
    completion: str = ''
    """Text to insert if the completion is specified. If empty the `trigger` will be inserted."""
    completion_format: int = 0
    """The format of the completion."""
    kind: tuple[int, str, str] = (0, '', '')
    """The kind of the completion."""
    details: str = ''
    """
    An optional minihtml description of the completion, shown in the detail pane at the bottom of
    the auto complete window.
    """
    flags: CompletionItemFlags = CompletionItemFlags.NONE


@dataclass
class Syntax:
    """Contains information about a syntax."""

    path: str = ''
    """The packages path to the syntax file."""
    name: str = ''
    """The name of the syntax."""
    hidden: bool = False
    """If the syntax is hidden from the user."""
    scope: str = ''
    """The base scope name of the syntax."""

    def __hash__(self) -> int:
        return hash((self.path, self.name, self.hidden, self.scope))


@dataclass
class QuickPanelItem:
    """Represents a row in the quick panel, shown via `Window.show_quick_panel()`."""

    trigger: str = ''
    """Text to match against user's input."""
    details: str | list[str] | tuple[str] = ''
    """A minihtml string or list of strings displayed below the trigger."""
    annotation: str = ''
    """Hint to draw to the right-hand side of the row."""
    kind: tuple[int, str, str] = (0, '', '')
    """The kind of the item."""


@dataclass
class ListInputItem:
    text: str = ''
    """Text to match against the user's input."""
    value: Any = ''
    """A `Value` passed to the command if the row is selected."""
    details: str | list[str] | tuple[str] = ''
    """A minihtml string or list of strings displayed below the trigger."""
    annotation: str = ''
    """Hint to draw to the right-hand side of the row."""
    kind: tuple[int, str, str] = (0, '', '')
    """The kind of the item."""


NULL_REGION = Region(0, 0)


@dataclass
class SymbolRegion:
    """Contains information about a `Region` of a `View` that contains a symbol."""

    name: str = ''
    """The name of the symbol."""
    region: Region = NULL_REGION
    """The location of the symbol within the `View`."""
    syntax: str = ''
    """The name of the syntax for the symbol."""
    type: int = 0
    """The type of the symbol"""
    kind: tuple[int, str, str] = (0, '', '')
    """The kind of the symbol."""


@dataclass
class SymbolLocation:
    """Contains information about a file that contains a symbol."""

    path: str = ''
    """The filesystem path to the file containing the symbol."""
    display_name: str = ''
    """The project-relative path to the file containing the symbol."""
    row: int = 0
    """The row of the file the symbol is contained on."""
    col: int = 0
    """The column of the row that the symbol is contained on."""
    syntax: str = ''
    """The name of the syntax for the symbol."""
    type: int = 0
    """The type of the symbol."""
    kind: tuple[int, str, str] = (0, '', '')
    """The kind of the symbol."""

    def path_encoded_position(self) -> str:
        """Return the path with the position encoded as a fragment."""
        return f'{self.path}:{self.row}:{self.col}'


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
    return str(PATHS.home / 'Packages')


def installed_packages_path() -> str:
    return str(PATHS.home / 'Installed Packages')


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
