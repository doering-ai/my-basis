############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import warnings
from typing import (
    ClassVar,
    TypeVar,
    Any,
    Union,
    Generic,
    Type,
    NamedTuple,
    Literal,
    get_args,
    get_origin,
    overload,
    cast,
)
from typing_extensions import TypeGuard, TypeAlias
from collections.abc import Callable, Sequence, Iterator, Generator, AsyncGenerator
from pathlib import Path
import inspect
import functools as ft
import itertools as it
import contextlib as ctx
import time
import asyncio as aio
from urllib.parse import unquote
import logging

### EXTERNAL
import sublime_plugin as sbp
import sublime as sb
from sublime import Region, Settings, Selection, View, Buffer, Window, Edit
import regex as re
import more_itertools as mi
import pydantic as pyd

### INTERNAL
from ..infra.utils import ut
from ..infra.PathRegistry import PathRegistry
from ..infra.ViewProperties import ViewProperties, view_property
from ..types.Comment import Comment
from ..types.StaticPrompt import StaticPrompt
from ..types.CommandArguments import CommandArguments

# pyright: reportSelfClsParameterName=false


############
### META ###
############
C = TypeVar("C", bound="MyBase")
R = TypeVar("R", bound=object)
Function = TypeVar("Function", bound=Callable)
InputHandler = sbp.CommandInputHandler
SublimeBases = (
    sbp.TextCommand,
    sbp.WindowCommand,
    sbp.ApplicationCommand,
    sbp.EventListener,
    sbp.ViewEventListener,
    sbp.TextChangeListener,
)
SublimeBase = Union[
    sbp.TextCommand,
    sbp.WindowCommand,
    sbp.ApplicationCommand,
    sbp.EventListener,
    sbp.ViewEventListener,
    sbp.TextChangeListener,
]
CommandLevel: TypeAlias = Literal["buffer", "view", "window", "app"]


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

    CACHED_TYPES: ClassVar[set[type]] = {View, Buffer, Window, Edit}
    ALLOWED_NAMES: ClassVar[re.Pattern] = re.compile(r"^([^_].*|__init__)$")

    @classmethod
    def __prepare__(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Chooses the dict subclass to be used for creating the namespace."""
        return _CustomNamespace()

    @classmethod
    def __new__(
        metacls,  # noqa: N804
        cls: MyBase,
        clsname: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        autobind: Sequence[str] | set[str] | bool = True,
        debug: bool | str = False,
        **kwargs: Any,
    ) -> type:
        """Wraps methods to store relevant argument(s)."""
        sb_base = Meta.find_sublime_base(bases)
        if sb_base and autobind is not False:
            sb_attrs = {
                key
                for key, val in sb_base.__dict__.items()
                if key and not key.startswith("_") and callable(val)
            }
            for name, value in namespace.items():
                # I. Wrap methods from base classes
                if metacls.do_bind_method(value, name, autobind, sb_attrs):
                    namespace[name] = metacls.bind_method(value)

        namespace["DEBUG"] = debug

        # Pass everything else along to type
        return super().__new__(metacls, clsname, bases, namespace, **kwargs)

    @staticmethod
    def find_sublime_base(bases: tuple[type, ...]) -> SublimeBase | None:
        next_bases = list(
            filter(
                (
                    lambda base: (
                        isinstance(base, type) and issubclass(base, SublimeBases)
                    )
                ),
                bases,
            )
        )
        if ret := next(filter(lambda b: b in SublimeBases, next_bases), None):
            return ret  # type: ignore
        _recur = lambda base: Meta.find_sublime_base(base.__bases__)
        return next(filter(bool, map(_recur, next_bases)), None)

    @classmethod
    def do_bind_method(
        cls,
        method: Any,
        name: str,
        autobind: Sequence[str] | set[str] | bool | None,
        sb_attrs: set[str],
    ) -> TypeGuard[Callable]:
        """Bind the method."""
        if not callable(method) or not cls.ALLOWED_NAMES.match(name):
            # I.i. Filter out obviously invalid attributes, like non-methods
            return False
        elif autobind and isinstance(autobind, (Sequence, set)):
            # I.ii. If the user supplied an override, only use that
            return name in autobind
        elif sb_attrs and name not in sb_attrs:
            # I.iii. If the method is not from a Sublime base class, ignore it
            return False
        elif name.startswith("is_"):
            # I.iv. Filter out likely boolean methods
            return False

        try:
            # II.i. Filter out methods that don't have at least one argument after `self`
            params = list(inspect.signature(method).parameters.items())
            if len(params) < 2 or params[0][0] != "self":
                return False

            # II.ii. Determine if any parameters are named-like or annotated-as a relevant type
            names, annotations = map(set, mi.unzip(params[1:]))
            _cnames, _ctypes = cls.cache_details()
            return bool(names & _cnames) or bool(annotations & _ctypes)

        except Exception:
            # III. Obviously, any unexpected failures mean 'no'
            warnings.warn(
                f"Failed to inspect method `{name}` for binding: {method!r}",
                stacklevel=3,
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
        for name, arg in it.chain((("", a) for a in args), kwargs.items()):
            if isinstance(arg, list) and (name == "views"):
                self.views = arg
            elif isinstance(arg, View) or (name == "view" and arg is None):
                self.view = arg
            elif isinstance(arg, Buffer) or (name == "buffer" and arg is None):
                self.buffer = arg
            elif isinstance(arg, Window) or (name == "window" and arg is None):
                self.window = arg
            elif isinstance(arg, Edit) or (name == "edit" and arg is None):
                self.edit = arg

    @staticmethod
    @ft.lru_cache(maxsize=1)
    def cache_details() -> tuple[set[str], set[type]]:
        return (
            {t.__name__.lower() for t in Meta.CACHED_TYPES},
            Meta.CACHED_TYPES,
        )


############
### DATA ###
############
class LineComment(NamedTuple):
    # ['region', 'row', 'col', 'text', 'mark']
    region: Region
    row: int
    col: int
    text: str
    punct: str

    def split(self, rhs: LineComment) -> bool:
        return self.row != rhs.row - 1 or self.col != rhs.col or self.punct != rhs.punct


class Indent(NamedTuple):
    """A list of (row, indent) pairs for each line in the view."""

    row: int
    val: int


RGXS = ut.rgx_dict(
    comment_punct=r"[[:punct:]]{1,3}",
    indent=r"(?m)^([ \t]*+)(\S?)",
    args=r'^(?P<cmd>[-\w]++) *(?:["\'](?P<key>\w+)["\']: *["\'](?P<val>.+?)["\'])*+$',
)
_I = TypeVar("_I", bound=CommandArguments)


############
### BODY ###
############
class MyBase(sbp.Command, Generic[_I], metaclass=Meta):
    """A base class for Sublime Text commands with utilities for comment handling."""

    _cache: ViewProperties

    _view: ut.ViewField | None = None
    _views: list[ut.ViewField] | None = None
    _buffer: ut.BufferField | None = None
    _window: ut.WindowField | None = None
    _edit: ut.EditField | None = None

    PATHS: ClassVar[PathRegistry] = ut.PATHS
    DEBUG: ClassVar[bool] = False
    _ALLOW_OVERRIDES: ClassVar[bool] = False
    Interface: ClassVar[Type[_I]]  # pyright: ignore
    _args: _I | None = None
    _raw_args: dict[str, Any] | None = None

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._cache = ViewProperties()

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the command with the given keyword arguments."""
        # self._log_func(args, kwargs)
        if args or kwargs:
            Meta.cache_args(self, args, kwargs)
        self.args = self.Interface(**kwargs)
        try:
            self.main()
        except Exception as error:
            self.catch(error)

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        for base in getattr(cls, "__orig_bases__", ()):
            origin = get_origin(base)
            if origin is MyBase or (
                isinstance(origin, type) and issubclass(origin, MyBase)
            ):
                if (
                    (type_args := get_args(base))
                    and isinstance(type_args[0], type)
                    and issubclass(type_args[0], CommandArguments)
                ):
                    cls.Interface = type_args[0]  # type: ignore

        if not getattr(cls, "Interface", None):
            cls.Interface = CommandArguments  # type: ignore

    def name(self) -> str:
        return getattr(type(self), "NAME", super().name())

    @property
    def uid(self) -> str:
        return f"{self.classname}[{str(id(self))[-4:]}]"

    @property
    def prompt(self) -> StaticPrompt | None:
        return self.Interface.PROMPT

    @property
    def args(self) -> _I:
        """The arguments passed to this command, as an instance of the `Interface` class."""
        assert self._args is not None, (
            "Called args-dependent method without setting `args`."
        )
        return self._args

    @args.setter
    def args(self, new_args: _I) -> None:
        self._args = new_args

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
        if self.prompt is None or args.get(self.prompt.keyword) is not None:
            return None
        return self.prompt.generate_input_handler(command=self, raw_args=args)()  # type: ignore

    def input_description(self) -> str:
        if self.prompt and (desc := self.prompt.prefix):
            return desc
        return super().input_description()

    # -------------------
    # `-` Private Methods
    # -------------------
    def _raw_line_comment_iter(self) -> Iterator[LineComment]:
        for comment in self.view.find_by_selector(
            "comment.line - punctuation.definition.comment"
        ):
            line = self.view.line(comment.begin())
            line_text = self.read(line)
            row, col = self.view.rowcol(comment.a)
            punct = line_text[:col].lstrip()
            if not RGXS["comment_punct"].fullmatch(punct):
                # Skip comments at the end of non-empty lines
                continue

            yield LineComment(line, row, col, line_text[col:], punct)

    @staticmethod
    def _path_for(filename: sb.View | str | None) -> Path:
        if isinstance(filename, sb.View):
            filename = filename.file_name()
        return Path(filename).expanduser().resolve() if filename is not None else Path()

    def _calc_indent(self, text: str) -> int:
        match = re.match(r" +", text.expandtabs(self.tabsize))
        return len(match[0]) if match else 0

    @overload
    def _line_content(self, *, row: int) -> tuple[Region, str]: ...

    @overload
    def _line_content(self, *, pos: int) -> tuple[Region, str]: ...

    def _line_content(self, *, row: int = -1, pos: int = -1) -> tuple[Region, str]:
        if pos < 0:
            assert row >= 0, "Must specify either a non-negative row or position."
            pos = self.view.text_point(row, 0)
        region = self.view.line(pos)
        text = self.read(region)
        indent = self._calc_indent(text)
        return Region(region.a + indent, region.b), text[indent:]

    # -------------------
    # `+` Primary Methods
    # -------------------
    @classmethod
    def _log(
        cls,
        *args: Any,
        data: dict | pyd.BaseModel | set | Sequence | None = None,
        sep: str = " ",
        time: bool = True,
        indent: pyd.NonNegativeInt = 0,
        rjust: int = 0,
        name: str | None = None,
        log_level: str | int = logging.INFO,
        **kwargs: Any,
    ) -> None:
        if log_level == logging.DEBUG and not cls.DEBUG:
            return

        # I. Normalize a name identifying the caller.
        if name is None:
            name = f"[{cls.__name__}]"
        elif name := name.strip():
            if not name.startswith("["):
                name = f"[{name}]"

        # II. Join the name and arguments into a single line
        parts = list(filter(bool, (name, *map(str, args))))
        ret = sep.join(parts)
        if time:
            ret = ut.posix().strftime("%H:%M:%S.%f")[:-3] + f" {ret}"

        # III. Print multiline data
        if data:
            ret = ut.multiprint(title=ret.rstrip(" :") + ":", data=data)

        # IV. Transform spacing
        if rjust:
            ret = "\n".join(line.rjust(rjust - indent) for line in ret.splitlines())
        elif indent:
            ret = re.sub(r"(?m)^(?!$)", " " * indent, ret)

        print(ret, **kwargs)

    def log(
        self,
        *args: Any,
        data: dict | pyd.BaseModel | set | Sequence | None = None,
        sep: str = " ",
        time: bool = True,
        indent: pyd.NonNegativeInt = 0,
        rjust: int = 0,
        name: str | None = None,
        log_level: str | int = logging.INFO,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("name", name or self.uid)
        self._log(
            *args,
            data=data,
            sep=sep,
            time=time,
            indent=indent,
            rjust=rjust,
            log_level=log_level,
            **kwargs,
        )

    def log_method(
        self,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
        result: str | None = None,
        name: str = "",
        log_level: str | int = logging.INFO,
        **log_kwargs: Any,
    ) -> None:
        if log_level == logging.DEBUG and not self.DEBUG:
            return

        if name:
            pass
        elif (frame := inspect.currentframe()) is not None and frame.f_back is not None:
            name = frame.f_back.f_code.co_name
        else:
            name = "<anon>"

        arg_parts = []
        if args:
            arg_parts.extend(map(str, args))
        if kwargs:
            arg_parts.extend(f"{k}={v}" for k, v in kwargs.items())

        _text = f"{name}({', '.join(arg_parts)})" + (f" -> {result}" if result else "")
        self._log(_text, log_level=log_level, **log_kwargs)

    @ctx.contextmanager
    def update_view_property(self, *names: str) -> Generator[dict[str, Any]]:
        missing = [n for n in names if n not in self._cache]
        assert not missing, (
            f"Tried to update non-existent view_properties ({missing=})."
        )
        values = {name: self._cache.values[name] for name in names}
        yield values
        count = self.view.change_count()
        for name, value in values.items():
            self._cache.counts[name] = count
            self._cache.values[name] = value
            if name in self._cache.hash_fns:
                self._cache.hashes[name] = hash(self._cache.hash_fns[name](self))

    @overload
    @ctx.contextmanager
    def with_context(self, *, view: View) -> Generator: ...

    @overload
    @ctx.contextmanager
    def with_context(self, *, buffer: Buffer) -> Generator: ...

    @overload
    @ctx.contextmanager
    def with_context(self, *, window: Window) -> Generator: ...

    @overload
    @ctx.contextmanager
    def with_context(self, *, edit: Edit) -> Generator: ...

    @ctx.contextmanager
    def with_context(
        self,
        *,
        view: View | None = None,
        buffer: Buffer | None = None,
        window: Window | None = None,
        edit: Edit | None = None,
    ) -> Generator:
        """A context manager that sets the given attribute to the given value."""
        old: dict = {}
        if view is not None:
            old["view"] = self._view
            old["views"] = self._views
            self.view = view
        elif buffer is not None:
            old["buffer"] = self._buffer
            self.buffer = buffer
        elif window is not None:
            old["window"] = self._window
            self.window = window
        elif edit is not None:
            old["edit"] = self._edit
            self.edit = edit
        try:
            yield
        finally:
            if "view" in old:
                self.view = old["view"]
                self.views = old["views"]
            if "buffer" in old:
                self.buffer = old["buffer"]
            elif "window" in old:
                self.window = old["window"]
            elif "edit" in old:
                self.edit = old["edit"]

    @ctx.asynccontextmanager
    async def with_view_async(self, path: Path | str, **kwargs: Any) -> AsyncGenerator:
        """An async context manager that creates a temporary view of the target file."""
        with self.with_context(view=await self.open_async(path, **kwargs)):
            if self.has_window():
                self.window.focus_view(self.view)
            yield

    @ctx.contextmanager
    def with_view(self, path: Path | str, **kwargs: Any) -> Generator:
        """A context manager that creates a temporary view of the target file."""
        with self.with_context(view=self.open(path, **kwargs)):
            if self.has_window():
                self.window.focus_view(self.view)
            yield

    def navigate(self, href: str) -> None:
        """Navigate to a code point from a hyperlink in an annotation popup."""
        href = unquote(href).strip()
        if href.startswith("file:"):
            self.open(href[5:].strip())
        elif href.startswith("http"):
            sb.run_command("open_url", {"url": href})
        elif href.startswith("subl:"):
            match = RGXS["args"].fullmatch(href[5:].strip())
            assert match, f"Invalid command href: {href!r}"
            data, captures = ut.clean_rgx_match(match)
            args: dict = dict(zip(captures["key"], captures["val"]))
            self.invoke(data["cmd"], **args)

    async def navigate_async(self, href: str) -> None:
        """Navigate to a code point from a hyperlink in an annotation popup."""
        href = unquote(href).strip()
        if href.startswith("file:"):
            await self.open_async(href[5:].strip())
        elif href.startswith("http"):
            sb.run_command("open_url", {"url": href})
        elif href.startswith("subl:"):
            match = RGXS["args"].fullmatch(href[5:].strip())
            assert match, f"Invalid command href: {href!r}"
            data, captures = ut.clean_rgx_match(match)
            args: dict = dict(zip(captures["key"], captures["val"]))
            await self.invoke_async(data["cmd"], **args)

    # ------------------
    # `x` Public Methods
    # ------------------
    def main(self) -> Any:
        """The primary entry point for the command.

        Not marked abstract so that the abstract classes can be instantiated by
        `sublime_plugin.load_module()`.
        Sadly, there's no way to prevent this other than changing their code.
        """
        raise NotImplementedError(
            "You must implement the `main` method to use this class."
        )

    def catch(self, error: Exception) -> None:
        """A standardized point to handle any errors that arise during the exection of `main()`."""
        raise error

    @ft.cached_property
    def classname(self) -> str:
        """The name of this command's class."""
        return self.name()

    @view_property(hash_by_syntax=True)
    def _syntax_vars(self) -> dict[str, str]:
        shell_vars = self.view.meta_info("shellVariables", 0)
        assert isinstance(shell_vars, list)
        return {item["name"]: item["value"] for item in shell_vars}

    @view_property(hash_by_syntax=True)
    def _comment_mark(self) -> str:
        return self._syntax_vars.get("TM_COMMENT_START", "#").strip()

    @view_property
    def indents(self) -> list[Indent]:
        matches = [
            (len(item[0].expandtabs(self.tabsize)), bool(item[1]))
            for item in RGXS["indent"].findall(self.read())
        ]
        match_len = len(matches)
        assert match_len == self.n_rows, "Indent count does not match line count."

        ret = []
        last = 0
        _iter = mi.groupby_transform(
            matches, keyfunc=lambda item: item[0], reducefunc=list
        )  # type: ignore
        _iter = cast("Iterator[tuple[int, list[tuple[int, bool]]]]", _iter)
        for indent, lines in _iter:
            size = len(lines)
            has_content = lines[0][1]
            start, end = last, last + size
            last = end
            if has_content and (not ret or indent != ret[-1].val):
                # Only count lines with one or more non-whitespace characters
                ret.append(Indent(start, indent))

        return ret

    def indent_at(self, row: int, indents: list[Indent] | None = None) -> Indent:
        if not (indents := self.indents):
            return Indent(0, 0)
        for _cur, _next in mi.pairwise(indents):
            if _cur.row <= row < _next.row:
                return _cur
        return indents[-1]

    def shares_indent(self, r0: int, r1: int, min_indent: int = 0) -> bool:
        """Whether indents imply the second line to be a child or sibling of the first.

        Args:
            r0: The row index of the first line (0-indexed).
            r1: The row index of the second line (0-indexed).
            min_indent: If set, the minimum indent required for both lines.
        """
        indents = self.indents
        i0, i1 = self.indent_at(r0, indents), self.indent_at(r1, indents)
        min_indent = min_indent or i0.val
        if i1.row < i0.row or not min_indent <= i0.val <= i1.val:
            return False
        elif i0 == i1:
            return True
        else:
            return all(
                ix.val >= min_indent
                for ix in indents[indents.index(i0) + 1 : indents.index(i1)]
            )

    # ----------------------
    # `x0` CACHED PROPERTIES
    # ----------------------
    @property
    def views(self) -> list[View]:
        """The particualr view (i.e. tab) associated with this command."""
        if self._views is None:
            self._infer_views()
        assert self._views is not None, (
            "Called views-dependent method without setting `views`."
        )
        return self._views

    @views.setter
    def views(self, new_views: list[View] | None) -> None:
        if (
            new_views is not None
            and self._views is not None
            and not self._ALLOW_OVERRIDES
        ):
            err = f"{self.classname} received a new list of views before the old ones were cleaned."
            assert len(self._views) == len(new_views), err
            assert all(v0 is v1 for v0, v1 in zip(self._views, new_views)), err
            return

        self._views = new_views

    @property
    def view(self) -> View:
        """The particualr view (i.e. tab) associated with this command."""
        if self._view is None:
            self._infer_view()
        assert self._view is not None, (
            "Called view-dependent method without setting any views."
        )

        if self.has_views():
            assert self._view in self.views, "Inferred view is not in views list."

        return self._view

    @view.setter
    def view(self, new_view: View | None) -> None:
        self._view = new_view
        if self._view is None:
            pass
        elif not self._views:
            self._views = [self._view]
        else:
            assert self._view in self._views, (
                f"{self.classname} received a new view that is not in the current views list."
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
                f"{self.classname} has multiple views but no view set; defaulting to the first.",
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
    def buffer(self) -> Buffer:
        """The Buffer (i.e. list of views) tied to this command."""
        assert self._buffer is not None, (
            "Called buffer-dependent method without setting `buffer`."
        )
        return self._buffer

    @buffer.setter
    def buffer(self, val: Buffer | None) -> None:
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
                f"{self.classname} received a new view object before the old one was cleaned."
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

    @property
    def window(self) -> Window:
        """The Window associated with this command."""
        if self._window is None:
            self._infer_window()
        assert self._window is not None, (
            "Called window-dependent method without setting `window` or `view`."
        )
        return self._window

    @window.setter
    def window(self, val: Window | None) -> None:
        if self.has_window() and val is not None and not self._ALLOW_OVERRIDES:
            assert self._window is val, (
                f"{self.classname} received a new window object before the old one was cleaned."
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

    @property
    def edit(self) -> Edit:
        """The Edit handle associated with this command (usually only for TextCommands)."""
        assert self._edit is not None, (
            "Called edit-dependent method without setting `edit`."
        )
        return self._edit

    @edit.setter
    def edit(self, val: Edit | None) -> None:
        """Set the new value of edit, possibly overriding an old one."""
        self._edit = val

    def has_edit(self) -> bool:
        """Whether this command currently has an Edit handle."""
        return self._edit is not None

    # -------------
    # `x2` SETTINGS
    # -------------
    @property
    def view_settings(self) -> Settings:
        """The settings object for this view."""
        return self.view.settings()

    @property
    def window_settings(self) -> Settings:
        """The settings object for this window."""
        return self.window.settings()

    @property
    def settings(self) -> Settings:
        """The most specific settings object available."""
        if self.has_view():
            return self.view_settings
        elif self.has_window():
            return self.window_settings
        elif window := mi.first(sb.windows(), None):
            return window.settings()
        else:
            raise RuntimeError("No windows found to get settings from.")

    @ctx.contextmanager
    def mutable_settings(self, filename: str) -> Generator[Settings]:
        """A context manager that lets you modify the identified settings file on disk."""
        # I. Clean & pre-verify the given filename
        assert filename, "Filename must be non-empty."
        _path = Path(filename)
        if not _path.suffix:
            _path = _path.with_suffix(".sublime-settings")
        assert len(_path.parts) == 1, (
            f'Filename "{_path}" must be a single name, not a path.'
        )
        filename = _path.name

        settings = sb.load_settings(filename)
        yield settings
        sb.save_settings(filename)

    @ft.cached_property
    def tabsize(self) -> int:
        return self.settings.get("tab_size", 4)

    # -----------------
    # `x3` VIEW METHODS
    # -----------------
    @property
    def v_id(self) -> ut.ViewId:
        return self.view.id()

    @overload
    def read(self, *args: Any, **kwargs: Any) -> str: ...

    @overload
    def read(self, region: int) -> str: ...

    @overload
    def read(self, region: int, end: int) -> str: ...

    @overload
    def read(self, region: Region) -> str: ...

    def read(self, region: Region | int = 0, end: int = 0) -> str:
        """Read the text in the given region."""
        if isinstance(region, int):
            region = sb.Region(region, end or len(self.view))
        assert isinstance(region, sb.Region), f"Invalid region argument {region!r}."
        return self.view.substr(region)

    def read_all(self, selector: str) -> Iterator[str]:
        """Iterate through all text in this view that matches the given selector."""
        for region in self.view.find_by_selector(selector):
            yield self.read(region)

    def write(self, pos: ut.ViewPosition, text: str) -> None:
        """Write the given text at the given position or region."""
        if isinstance(pos, int):
            pos = Region(pos, pos)
        elif isinstance(pos, tuple):
            pos = Region(pos[0], pos[1])
        assert isinstance(pos, Region)

        if pos.empty():
            self.view.insert(self.edit, pos.a, text)
        else:
            self.view.replace(self.edit, pos, text)

    @ctx.contextmanager
    def batch_write(self, debug: bool | None = None) -> Generator[ut.Writer]:
        # return ut.batch_write(self.write, self.DEBUG if debug is None else debug)
        with ut.batch_write(
            self.view, self.edit, self.DEBUG if debug is None else debug
        ) as writer:
            yield writer

    def show(
        self,
        dest: Region | int | None,
        mode: Literal["normal", "top", "center", "bottom"] = "normal",
        select: bool = True,
        **kwargs: Any,
    ) -> None:
        """Show the given region or position in the view, selecting it."""
        # I. Normalize the arguments
        if isinstance(dest, int):
            dest = Region(dest, dest)
        elif dest is None:
            dest = self.selection

        # II. Change the selection if asked
        if select:
            self.selections.clear()
            self.selections.add(dest)

        if mode == "normal":
            # III.i. Base case: scroll using Sublime's automated features
            self.view.show(dest, **kwargs)
        elif mode == "center":
            # III.ii. Scroll so that the point is centered, again using premade features
            self.view.show_at_center(dest, **kwargs)
        else:
            # III.iii. Finally, scroll so that the targeted line is either at the top or the bottom
            #          of the screen using logic borrowed from Vintage.
            screen = self.view.visible_region()
            orig_line = self.view.rowcol(
                screen.begin() if mode == "top" else screen.end()
            )[0]
            dest_line = self.view.rowcol(dest.begin())[0]
            offset = dest_line - orig_line
            self.view.run_command("scroll_lines", {"amount": -offset})

    def write_comment(self, comment: Comment) -> int:
        """Write the given Comment back to the view."""
        old = self.read(comment.region)
        new = str(comment)
        if old != new:
            self.write(comment.region, new)
            return len(new) - len(old)
        return 0

    def find_within(self, selector: str, region: Region) -> Iterator[Region]:
        """Find all regions matching the given selector within the given region."""
        yield from filter(region.contains, self.view.find_by_selector(selector))

    def find_iter(
        self, selector: str, region: Region | None = None
    ) -> Iterator[Region]:
        """Simple wrapper for `find_by_selector` that returns a view instead of a list."""
        if region is not None:
            yield from self.find_within(selector, region)
        else:
            yield from iter(self.view.find_by_selector(selector))

    @view_property(scopes=("comment.line",))
    def line_comments(self) -> dict[int, Comment]:
        ret = {
            block[0].row: Comment(
                lines=[line.region for line in block],
                texts=[line.text.rstrip("\n") for line in block],
                row=block[0].row,
                col=block[0].col,
                punct=block[0].punct,
            )
            for block in mi.split_when(self._raw_line_comment_iter(), LineComment.split)
        }
        return ret

    def filter_comments(
        self,
        *preds: Callable[[Comment], bool],
        start: int = 0,
        end: int = 0,
        min_height: int = 1,
    ) -> Iterator[Comment]:
        """Iterate through a subset of the comments found in this file.

        Args:
            preds: Predicate functions to filter comments by.
            start: The starting point of the region to search for comments.
            end: The ending point of the region to search for comments (if not EOF).
            min_height: If set, only returns comment blocks with at least this many lines.
        Yields:
            Comment objects. Continuous series are merged & yielded together.
        """
        filters = list(preds)
        if start or end:
            assert start >= 0 and (start < end or end == 0), (
                "Start and end must be non-negative."
            )
            bounds = Region(start, end or self.view.size())
            filters.append(lambda comment: bounds.contains(comment.region))

        if min_height > 1:
            filters.append(lambda comment: comment.height >= min_height)

        if filters:
            yield from filter(
                lambda comment: all(f(comment) for f in filters),
                self.line_comments.values(),
            )
        else:
            yield from self.line_comments.values()

    @view_property
    def function_map(self) -> dict[str, sb.Region]:
        ret = {}
        for region in self.view.find_by_selector("entity.name.function"):
            name = self.view.substr(region)
            if name not in ret:
                ret[name] = region
        return ret

    @view_property
    def class_map(self) -> dict[str, sb.Region]:
        ret = {}
        for region in self.view.find_by_selector("entity.name.class"):
            name = self.view.substr(region)
            if name not in ret:
                ret[name] = region
        return ret

    @overload
    def first_char_of(self, *, pos: int = -1) -> int: ...

    @overload
    def first_char_of(self, *, row: int = -1) -> int: ...

    def first_char_of(self, *, pos: int = -1, row: int = -1) -> int:
        # if row < 0:
        #     assert pos >= 0, 'Must specify either a non-negative position or row.'
        #     row = self.view.rowcol(pos)[0]
        if pos < 0:
            assert row >= 0, "Must specify either a non-negative position or row."
            pos = self.view.text_point(row, 0)

        bol = self.view.text_point(row, 0)
        line = self.read(self.view.line(bol))
        if match := RGXS["indent"].match(line):
            return pos + len(match[1])
        return pos

    def row_of(self, pos: Region | int) -> int:
        """The row index of the given position."""
        if isinstance(pos, sb.Region):
            pos = pos.begin()
        return self.view.rowcol(pos)[0]

    def col_of(self, pos: Region | int) -> int:
        """The column index of the given position."""
        if isinstance(pos, sb.Region):
            pos = pos.begin()
        return self.view.rowcol(pos)[1]

    @property
    def selections(self) -> Selection:
        """The regions currently selected in the view."""
        return self.view.selection

    @property
    def selection(self) -> Region:
        """The first group of selected text, ignoring multi-cursor situations."""
        return mi.first(self.selections, Region(0, 0))

    @property
    def cursors(self) -> Iterator[int]:
        """The position of all cursors, which may be the beginning OR end of their selections."""
        yield from (region.b for region in self.selections)

    @property
    def cursor(self) -> int:
        """The position of the first cursor, which may be the beginning OR end of its selection."""
        return mi.first(self.cursors, 0)

    @property
    def pos(self) -> int:
        """The position of the beginning of the first selection."""
        return self.selection.begin()

    @property
    def lines(self) -> Iterator[Region]:
        """A list of unique lines that covers all selections."""
        yield from mi.unique_justseen(mi.flatten(map(self.view.lines, self.selections)))

    @property
    def first_lines(self) -> Iterator[Region]:
        """The first lines of the currently selected regions in the view."""
        yield from map(self.view.line, self.cursors)

    @property
    def line(self) -> Region:
        """The first line of the currently selected region in the view."""
        return mi.first(self.first_lines, Region(0, 0))

    @property
    def coords(self) -> Iterator[tuple[int, int]]:
        yield from map(self.view.rowcol, self.cursors)

    @property
    def rows(self) -> Iterator[int]:
        """The row index of each cursor."""
        yield from (row for row, _ in self.coords)

    @property
    def n_rows(self) -> int:
        return self.view.rowcol(self.view.size())[0] + 1

    @property
    def row(self) -> int:
        """The row index of the first cursor."""
        return mi.first(self.rows, 0)

    @property
    def cols(self) -> Iterator[int]:
        """The column index of each cursor."""
        yield from (col for _, col in self.coords)

    @property
    def col(self) -> int:
        """The column index of the first cursor."""
        return mi.first(self.cols, 0)

    @property
    def syntax(self) -> str:
        """The simplified syntax of the current view."""
        return inst.scope if (inst := self.view.syntax()) is not None else ""

    def syntax_is(self, *args: str) -> bool:
        """Whether the current view's syntax matches any of the given ones."""
        syn = self.syntax
        return any(arg in syn for arg in args)

    @property
    def path(self) -> Path:
        return self._path_for(self.view.file_name())

    # ------------------------
    # `*4` APPLICATION METHODS
    # ------------------------
    @property
    def api_level(self) -> CommandLevel:
        """The *primary* level at which this command lives."""
        if isinstance(self, (sbp.TextCommand, sbp.ViewEventListener)):
            return "view"
        elif isinstance(self, sbp.WindowCommand):
            return "window"
        elif isinstance(self, sbp.TextChangeListener):
            return "buffer"
        elif isinstance(self, (sbp.ApplicationCommand, sbp.EventListener)):
            return "app"
        raise RuntimeError(
            f"Unknown bases for {self.classname}: {self.__class__.__bases__}"
        )

    def invoke(
        self,
        command: str,
        /,
        _delay: int = 50,
        _async: bool = False,
        _level: CommandLevel | None = None,
        **kwargs: Any,
    ) -> None:
        """Invoke another command with the given arguments.

        Args:
            command: The name of the command to invoke.
            _delay: Milliseconds to wait before running the command.
            _async: If True, schedule via `sublime.set_timeout_async` (ST worker thread).
            _level: Explicit command level to invoke at, overriding inference.
            **kwargs: Arguments passed through to the invoked command.
        """
        fn: Callable[[str, dict], None]
        if _level is not None:
            if _level == "buffer":
                raise NotImplementedError(
                    "Invoking commands at the buffer level is not supported."
                )
            elif _level == "app":
                fn = sb.run_command
            else:
                fn = getattr(self, _level).run_command
        elif self._view is not None:
            fn = self.view.run_command
        elif self._window is not None:
            fn = self.window.run_command
        else:
            fn = sb.run_command

        timer = sb.set_timeout_async if _async else sb.set_timeout
        timer(lambda: fn(command, kwargs), _delay)

    async def invoke_async(
        self,
        command: str,
        /,
        _delay: int = 50,
        _async: bool = False,
        _level: CommandLevel | None = None,
        **kwargs: Any,
    ) -> None:
        """Asynchronously invoke another command with the given arguments."""
        fn = ft.partial(
            self.invoke, command, _delay=_delay, _async=_async, _level=_level, **kwargs
        )
        await aio.get_event_loop().run_in_executor(None, fn)

    @property
    def current_package(self) -> Path | None:
        window = self._window or sb.active_window()
        folders = set(
            mi.flatten(
                (path.name, path.resolve().name)
                for folder in window.folders()
                if (path := Path(folder).expanduser())
            )
        )
        return next(
            (
                pkg
                for pkg in self.PATHS.pkgs.iterdir()
                if pkg.name in folders or pkg.resolve().name in folders
            ),
            None,
        )

    # -------------------
    # `*5` WINDOW METHODS
    # -------------------
    @property
    def w_id(self) -> ut.WindowId:
        return self.window.id()

    @property
    def cur_window(self) -> Window:
        """The Window associated with this command, or the active window if none is set."""
        return self.window if self.has_window() else sb.active_window()

    @property
    def folders(self) -> list[Path]:
        """The list of folders in the current window, resolved to absolute paths."""
        return list(map(ut.path, self.cur_window.folders()))

    @property
    def folder(self) -> Path:
        # Try our window's folder, then any window's folder, then the current file's project root
        if _ff := self.folders:
            return _ff[0]

        if _ffs := next(iter(ut.open_folders().values()), None):
            return next(_ffs)  # pyrefly: ignore[bad-argument-type]

        if self.has_view():
            return ut.path(self.view.file_name() or "").parent
        return Path.cwd()

    def open(
        self,
        path: Path | str,
        *,
        row: int = -1,
        flags: sb.NewFileFlags | None = None,
        window: sb.Window | None = None,
        group: int = -1,
    ) -> View:
        """Open the given file in a new view.

        Args:
            path: The path to the file to open.
            row: If set, the row to scroll to after opening the file.
            flags: Additional flags to pass to `window.open_file()`.
            window: If set, the window to open the file in rather than the current one.
            group: The group to open the file in, or -1 to let Sublime decide.
        """
        # I. Normalize arguments
        if flags is None:
            flags = sb.NewFileFlags(0)
        window = window or self.cur_window

        path = ut.normalize_path(path, window)
        pathstr = str(path)
        if row > -1:
            flags |= sb.NewFileFlags.ENCODED_POSITION
            pathstr += f":{row}"

        # III. Actually open the file and wait up to 3s for it to load
        view = window.open_file(pathstr, flags, group)
        count = 0
        while view.is_loading() and count < 30:
            time.sleep(0.1)
            count += 1
        if count == 30:
            warnings.warn(f'File "{pathstr}" took over 3s to load.', stacklevel=3)
        return view

    async def open_async(
        self,
        path: Path | str,
        *,
        row: int = -1,
        flags: sb.NewFileFlags | None = None,
        window: sb.Window | None = None,
        group: int = -1,
    ) -> View:
        """Asynchronously open the given file in a new view."""
        fn = ft.partial(
            self.open, path=path, row=row, flags=flags, window=window, group=group
        )
        return await aio.get_event_loop().run_in_executor(None, fn)
