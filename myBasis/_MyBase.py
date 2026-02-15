############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import warnings
from typing import ClassVar, TypeVar, Any, Union, Generic, Type, get_args, get_origin, TYPE_CHECKING
from typing_extensions import TypeGuard
from collections.abc import Callable, Sequence
from pathlib import Path
import inspect
import functools as ft
import itertools as it
import contextlib as ctx

if TYPE_CHECKING:
    from .StaticPrompt import StaticPrompt
    from collections.abc import Iterator

### EXTERNAL
import sublime_plugin as sbp
import sublime as sb
import regex as re
import more_itertools as mi

### INTERNAL
from .Comment import Comment
from .CommandArguments import CommandArguments

if TYPE_CHECKING:
    from .utils import Utils

############
### META ###
############
Function = TypeVar('Function', bound=Callable)
InputHandler = sbp.CommandInputHandler
SublimeBases = (
    sbp.Command,
    sbp.EventListener,
    sbp.ViewEventListener,
    sbp.TextChangeListener,
)
SublimeBase = Union[
    sbp.Command,
    sbp.EventListener,
    sbp.ViewEventListener,
    sbp.TextChangeListener,
]

# pyright: reportSelfClsParameterName=false
# ruff: noqa: UP035, UP006


class _CustomNamespace(dict):
    def __setitem__(self, key: str, new: object) -> None:
        if (old := self.get(key, None)) is not None and new is not old:
            # I. Keep whichever one is a property getter/setter (rather than a member variable)
            if isinstance(new, property):
                pass
            elif isinstance(old, property):
                return

        return super().__setitem__(key, new)


class Meta(type):
    """Metaclass that wraps all methods whose argument is a View, Buffer, or Window."""

    CACHED_TYPES: ClassVar[set[type]] = {sb.View, sb.Buffer, sb.Window, sb.Edit}
    ALLOWED_NAMES: ClassVar[re.Pattern] = re.compile(r'^([^_].*|__init__)$')

    @classmethod
    def __prepare__(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Chooses the dict subclass to be used for creating the namespace."""
        return _CustomNamespace()

    @classmethod
    def __new__(
        metacls,  # noqa: N804
        cls,
        clsname: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        autobind: Sequence[str] | set[str] | bool = True,
        **kwargs: Any,
    ) -> type:
        """Wraps methods to store relevant argument(s)."""
        if autobind is not False:
            if sublime_bases := [
                b for b in bases if isinstance(b, type) and issubclass(b, SublimeBases)
            ]:
                for name, value in namespace.items():
                    # I. Wrap methods from base classes
                    if cls.do_bind_method(value, name, autobind, sublime_bases):
                        namespace[name] = cls.bind_method(value)

        # Pass everything else along to type
        return super().__new__(cls, clsname, bases, namespace, **kwargs)

    @classmethod
    def do_bind_method(
        cls,
        method: Any,
        name: str,
        autobind: Sequence[str] | set[str] | bool | None,
        sublime_bases: list[type[SublimeBase]],
    ) -> TypeGuard[Callable]:
        if not callable(method) or not cls.ALLOWED_NAMES.match(name):
            # I.i. Filter out obviously invalid attributes, like non-methods
            return False
        elif autobind and isinstance(autobind, (Sequence, set)):
            # I.ii. If the user supplied an override, only use that
            return name in autobind
        elif sublime_bases and not any(name in base.__dict__ for base in sublime_bases):
            # I.iii. If the method is not from a Sublime base class, ignore it
            return False
        elif name.startswith('is_'):
            # I.iv. Filter out likely boolean methods
            return False

        try:
            # II.i. Filter out methods that don't have at least one argument after `self`
            params = list(inspect.signature(method).parameters.items())
            if len(params) < 2 or params[0][0] != 'self':
                return False

            # II.ii. Determine if any parameters are named-like or annotated-as a relevant type
            names, annotations = map(set, mi.unzip(params[1:]))
            _cnames, _ctypes = cls.cache_details()
            return bool(names & _cnames) or bool(annotations & _ctypes)

        except Exception:
            # III. Obviously, any unexpected failures mean 'no'
            warnings.warn(
                f'Failed to inspect method `{name}` for binding: {method!r}', stacklevel=3
            )
            return False

    @classmethod
    def bind_method(cls, method: Function) -> Function:
        """Wraps a method to store its first argument if it's a View, Buffer, or Window."""

        @ft.wraps(method)
        def wrapper(self: MyBase, *args: Any, **kwargs: Any) -> Any:
            cls.cache_args(self, args, kwargs)
            return method(self, *args, **kwargs)

        return wrapper  # type:ignore[invalid-return-type]

    @staticmethod
    def cache_args(self: MyBase, args: tuple, kwargs: dict) -> None:
        for name, arg in it.chain((('', a) for a in args), kwargs.items()):
            if isinstance(arg, list) and (name == 'views'):
                self.views = arg
            elif isinstance(arg, sb.View) or (name == 'view' and arg is None):
                self.view = arg
            elif isinstance(arg, sb.Buffer) or (name == 'buffer' and arg is None):
                self.buffer = arg
            elif isinstance(arg, sb.Window) or (name == 'window' and arg is None):
                self.window = arg
            elif isinstance(arg, sb.Edit) or (name == 'edit' and arg is None):
                self.edit = arg

    @staticmethod
    @ft.lru_cache(maxsize=1)
    def cache_details() -> tuple[set[str], set[type]]:
        return (
            {t.__name__.lower() for t in Meta.CACHED_TYPES},
            Meta.CACHED_TYPES,
        )

    @staticmethod
    @ctx.contextmanager
    def context(self: MyBase) -> Iterator[None]:
        """A context manager that sets the given attribute to the given value."""
        try:
            yield
        finally:
            self.views = None
            self.view = None
            self.buffer = None
            self.window = None
            self.edit = None


_I = TypeVar('_I', bound=CommandArguments)


############
### BODY ###
############
class MyBase(sbp.Command, Generic[_I], metaclass=Meta):  # noqa: UP046
    """A base class for Sublime Text commands with utilities for comment handling."""

    _view: Utils.ViewField | None = None
    _views: list[Utils.ViewField] | None = None
    _buffer: Utils.BufferField | None = None
    _window: Utils.WindowField | None = None
    _edit: Utils.EditField | None = None

    _ALLOW_OVERRIDES: ClassVar[bool] = False
    Interface: ClassVar[Type[_I]]  # pyright: ignore
    prompt: StaticPrompt | None = None
    _args: _I | None = None

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Run the command with the given keyword arguments."""
        if args:
            Meta.cache_args(self, args, kwargs)
        self.args = self.Interface(**kwargs)

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, '__orig_bases__', ()):
            origin = get_origin(base)
            if origin is MyBase or (isinstance(origin, type) and issubclass(origin, MyBase)):
                args = get_args(base)
                if args and isinstance(args[0], type) and issubclass(args[0], CommandArguments):
                    cls.Interface = args[0]  # type: ignore

        if not getattr(cls, 'Interface', None):
            cls.Interface = CommandArguments  # type: ignore

    def input(self, args: dict[str, Any]) -> InputHandler | None:
        """Prompt the user for input before running this command.

        It's very likely that your command just needs one or more pieces of basic text input, in
        which case you can set a default value for the `prompt` member variable.

        To add a *dynamic* input handler to your command, just override this command with one that
        returns a `sbp.TextInputHandler` (for a textarea) or a `sbp.ListInputHandler` (for a
        dropdown).

        The results of your input (as specified by the `name` property) can be found in
        `self.kwargs`; just like other command arguments, you can specify a member variable with
        the same name in your class to have it automatically filled with the input value.
        """
        return self.prompt.generate_input_handler()() if self.prompt else None

    @property
    def args(self) -> _I:
        """The arguments passed to this command, as an instance of the `Interface` class."""
        assert self._args is not None, 'Called args-dependent method without setting `args`.'
        return self._args

    @args.setter
    def args(self, new_args: _I) -> None:
        self._args = new_args

    # -------------------
    # `-` Private Methods
    # -------------------
    def _syntax_vars(self, pos: int = 0) -> dict[str, str]:
        shell_vars = self.view.meta_info('shellVariables', pos)
        assert isinstance(shell_vars, list)
        return {item['name']: item['value'] for item in shell_vars}

    def _comment_mark(self, pos: int = 0) -> str:
        syntax_vars = self._syntax_vars(pos)
        return syntax_vars.get('TM_COMMENT_START', '#').strip(' ')

    def _parse_comment(self, region: sb.Region) -> Comment:
        """Parse a comment from the given region."""
        data = {}
        data['lines'] = self.view.lines(region)
        assert data['lines'], 'No lines found in comment region.'

        raw_texts = list(map(self.read, data['lines']))
        data['texts'] = [text.strip(' \t') for text in raw_texts]

        # Read the line number (row) and indentation (column) of the comment's first line
        data['row'], _ = self.view.rowcol(region.begin())
        match = re.match(r'^\s*(?=\S)', raw_texts[0])
        assert match is not None
        data['col'] = len(match.group(0).replace('\t', '    ')) + 1

        # Remove the comment mark from texts, recording if it has been repeated for depth
        data['mark'] = mark = self._comment_mark(region.begin())
        for i, text in enumerate(data['texts']):
            if not text.startswith(mark):
                continue
            elif match := re.fullmatch(rf'({mark}+) (\S.*)', text):
                data['mark'], data['texts'][i] = match.groups()

        return Comment(**data)

    def _raw_comment_iter(self, start: int = 0, end: int = 0) -> Iterator[Comment]:
        end = end or self.view.size()
        for region in self.view.find_by_selector('comment.line'):
            if region and region.begin() <= start < end <= region.end():
                yield self._parse_comment(region)

    def _yield_comment(
        self, comment: Comment, target: int = 0, windowed: bool = False
    ) -> Iterator[Comment]:
        n = comment.n_lines
        if target > 0 and n != target:
            if windowed and (n_windows := n - target + 1) > 0:
                for i in range(n_windows):
                    yield comment[i : i + target]
        else:
            yield comment

    # -------------------
    # `+` Primary Methods
    # -------------------
    def read(self, region: sb.Region) -> str:
        """Read the text in the given region."""
        return self.view.substr(region)

    def write(self, pos: Union[sb.Region, tuple[int, int], int], text: str) -> None:
        """Write the given text at the given position or region."""
        if isinstance(pos, int):
            self.view.insert(self.edit, pos, text)
        elif isinstance(pos, tuple):
            pos = sb.Region(pos[0], pos[1])  # type: ignore

        assert isinstance(pos, sb.Region)
        self.view.replace(self.edit, pos, text)

    def show(self, region: Union[sb.Region, int]) -> None:
        """Show the given region or position in the view, selecting it."""
        if isinstance(region, int):
            region = sb.Region(region, region)

        self.selection.clear()
        self.selection.add(region)
        self.view.show(region)

    def write_comment(self, comment: Comment) -> int:
        """Write the given Comment back to the view."""
        old_text = self.read(comment.region)
        new_text = str(comment)
        if old_text != new_text:
            self.write(comment.region, new_text)

            new_region = sb.Region(comment.start, comment.start + len(new_text))
            _parsed = self._parse_comment(new_region)
            comment.lines = _parsed.lines
            comment.texts = _parsed.texts
            comment.row = _parsed.row
            comment.col = _parsed.col

            return len(new_text) - len(old_text)
        return 0

    def comment_iter(
        self,
        /,
        start: int = 0,
        end: int = 0,
        target: int = 0,
        windowed: bool = False,
    ) -> Iterator[Comment]:
        """Iterate through the comments found in this file, yielding Comment objects.

        Args:
            pos: The position in the file to start searching from.
            target: If set, only yield comments with exactly this many lines.
            windowed: If true, break up longer comments to fit the filter.
        Yields:
            Comment objects. Continuous series are merged & yielded together.
        """
        queued: Comment | None = None
        _yield = ft.partial(self._yield_comment, target=target, windowed=windowed)

        # Rely on Sublime Text's syntax system to find (non-block) comments
        for cur in self._raw_comment_iter(start=start, end=end):
            if queued is None:
                queued = cur
            elif cur.follows(queued):
                queued += cur
            else:
                yield from _yield(queued)
                queued = cur

        if queued:
            yield from _yield(queued)

    # ------------------
    # `x` Public Methods
    # ------------------
    @ft.cached_property
    def classname(self) -> str:
        """The name of this command's class."""
        return self.name()

    # --------------------
    # `x0` VIEW PROPERTIES
    # --------------------
    @property
    def views(self) -> list[sb.View]:
        """The particualr view (i.e. tab) associated with this command."""
        if self._views is None:
            self._infer_views()
        assert self._views is not None, 'Called views-dependent method without setting `views`.'
        return self._views

    @views.setter
    def views(self, new_views: list[sb.View] | None) -> None:
        if new_views is not None and self._views is not None and not self._ALLOW_OVERRIDES:
            err = f'{self.classname} received a new list of views before the old ones were cleaned.'
            assert len(self._views) == len(new_views), err
            assert all(v0 is v1 for v0, v1 in zip(self._views, new_views)), err  # noqa: B905
            return

        self._views = new_views

    @property
    def view(self) -> sb.View:
        """The particualr view (i.e. tab) associated with this command."""
        if self._view is None:
            self._infer_view()
        assert self._view is not None, 'Called view-dependent method without setting any views.'

        if self.has_views():
            assert self._view in self.views, 'Inferred view is not in views list.'

        return self.views[0]

    @view.setter
    def view(self, new_view: sb.View | None) -> None:
        self._view = new_view
        if self._view is None:
            pass
        elif not self._views:
            self._views = [self._view]
        else:
            assert self._view in self._views, (
                f'{self.classname} received a new view that is not in the current views list.'
            )

    def _infer_views(self) -> None:
        if self._views is not None:
            return
        elif self._buffer is not None:
            self._views = self._buffer.views()
        elif self._window is not None:
            self._views = self._window.views()
        elif self._view is not None:
            self._views = [self._view]

    def _infer_view(self) -> None:
        if self._view is not None:
            return
        elif self._views is not None and len(self._views) == 1:
            self._view = self.views[0]
        elif self._window is not None and (_v := self._window.active_view()):
            self._view = _v
        elif self._buffer is not None:
            self._view = self._buffer.primary_view()
        elif self._views is not None and len(self._views) > 0:
            warnings.warn(
                f'{self.classname} has multiple views but no view set; defaulting to the first.',
                stacklevel=3,
            )
            self._view = self._views[0]

    def has_views(self) -> bool:
        """Whether this command currently has a View handle."""
        if self._views is None:
            self._infer_views()
        return self._views is not None

    def has_view(self) -> bool:
        """Whether this command currently has a View handle."""
        if self._view is None:
            self._infer_view()
        return self._view is not None

    @property
    def regions(self) -> Iterator[sb.Region]:
        """The regions currently selected in the view."""
        yield from self.view.sel()

    @property
    def points(self) -> Iterator[int]:
        """The starting points of the currently selected regions in the view."""
        yield from (region.begin() for region in self.regions)

    @property
    def lines(self) -> Iterator[sb.Region]:
        """All lines intersecting with all selections in the the view."""
        yield from mi.unique_justseen(mi.flatten(map(self.view.lines, self.regions)))

    @property
    def first_lines(self) -> Iterator[sb.Region]:
        """The first lines of the currently selected regions in the view."""
        yield from map(self.view.full_line, self.points)

    @property
    def selection(self) -> sb.Selection:
        """The currently selected text, which is essentially just a collection of regions."""
        return self.view.sel()

    @property
    def position(self) -> int:
        """The starting position of the first selected region in the view."""
        return self.selection[0].begin()

    @property
    def syntax(self) -> str:
        """The simplified syntax of the current view."""
        return self.view_settings.get('syntax', '').lower()

    def syntax_is(self, *args: str) -> bool:
        """Whether the current view's syntax matches any of the given ones."""
        syn = self.syntax
        return any(arg in syn for arg in args)

    # ----------------------
    # `x2` BUFFER PROPERTIES
    # ----------------------
    @property
    def buffer(self) -> sb.Buffer:
        """The Buffer (i.e. list of views) tied to this command."""
        assert self._buffer is not None, 'Called buffer-dependent method without setting `buffer`.'
        return self._buffer

    @buffer.setter
    def buffer(self, val: sb.Buffer | None) -> None:
        if val is None:
            pass
        elif self._ALLOW_OVERRIDES:
            self.views = val.views()
            if self._view not in self.views:
                warnings.warn(
                    f"{self.classname} set to a buffer that doesn't relate to its current view.",
                    stacklevel=3,
                )
            self._view = val.primary_view()
            self._window = None

        elif self._buffer is not None:
            assert self._buffer is val, (
                f'{self.classname} received a new view object before the old one was cleaned.'
            )
            return
        self._buffer = val

    def infer_buffer(self) -> None:
        if self._buffer is not None:
            return
        elif self._view is None:
            if self._views is not None and len(self._views) == 1:
                self._view = self._views[0]
            elif self._window is not None and len(self._window.views()) == 1:
                self._views = self._window.views()
                self._view = self._views[0]

        if self._view is not None:
            self._buffer = self._view.buffer()

    def has_buffer(self) -> bool:
        """Whether this command currently has a Buffer handle."""
        return self._buffer is not None

    # ----------------------
    # `x3` WINDOW PROPERTIES
    # ----------------------
    @property
    def window(self) -> sb.Window:
        """The Window associated with this command."""
        if self._window is None:
            self._infer_window()
        assert self._window is not None, (
            'Called window-dependent method without setting `window` or `view`.'
        )
        return self._window

    @window.setter
    def window(self, val: sb.Window | None) -> None:
        if self.has_window() and val is not None and not self._ALLOW_OVERRIDES:
            assert self._window is val, (
                f'{self.classname} received a new window object before the old one was cleaned.'
            )
            return
        self._window = val

    def _infer_window(self) -> None:
        if self._window is not None:
            return
        elif self._view is not None:
            self._window = self._view.window()
        elif self._views:
            if len(self._views) > 1:
                first = self._views[0].window()
                if not all(view.window() is first for view in self._views[1:]):
                    return
            self._window = self._views[0].window()

    def has_window(self) -> bool:
        """Whether this command currently has a Window or View handle."""
        if self._window is None:
            self._infer_window()
        return self._window is not None

    # --------------------
    # `x3` EDIT PROPERTIES
    # --------------------
    @property
    def edit(self) -> sb.Edit:
        """The Edit handle associated with this command (usually only for TextCommands)."""
        assert self._edit is not None, 'Called edit-dependent method without setting `edit`.'
        return self._edit

    @edit.setter
    def edit(self, val: sb.Edit | None) -> None:
        """Set the new value of edit, possibly overriding an old one."""
        self._edit = val

    def has_edit(self) -> bool:
        """Whether this command currently has an Edit handle."""
        return self._edit is not None

    # -------------
    # `x4` SETTINGS
    # -------------
    @property
    def view_settings(self) -> sb.Settings:
        """The settings object for this view."""
        return self.view.settings()

    @property
    def window_settings(self) -> sb.Settings:
        """The settings object for this window."""
        return self.window.settings()

    @property
    def local_settings(self) -> sb.Settings:
        """The settings object for this window OR view, preferring the former."""
        return self.window_settings if self.has_window() else self.view_settings

    @ctx.contextmanager
    def mutable_settings(self, filename: str) -> Iterator[sb.Settings]:
        """A context manager that lets you modify the identified settings file on disk."""
        # I. Clean & pre-verify the given filename
        assert filename, 'Filename must be non-empty.'
        _path = Path(filename)
        if not _path.suffix:
            _path = _path.with_suffix('.sublime-settings')
        assert len(_path.parts) == 1, f'Filename "{_path}" must be a single name, not a path.'
        filename = _path.name

        settings = sb.load_settings(filename)
        yield settings
        sb.save_settings(filename)

    def main(self) -> Any:
        """The primary entry point for the command, executed when the command is.

        Not marked abstract so that the abstract classes can be instantiated by
        `sublime_plugin.load_module()`.
        Sadly, there's no way to prevent this other than changing their code.
        """
