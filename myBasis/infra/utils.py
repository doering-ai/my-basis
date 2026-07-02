############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from collections import defaultdict, deque
from collections.abc import (
    Callable,
    Iterator,
    Sequence,
    MutableSequence,
    Iterable,
    Collection,
    Generator,
)
from pathlib import Path
from types import FunctionType
from typing import ClassVar, TypeVar, Any, Literal, Union, NamedTuple, overload
from typing_extensions import TypeAlias, ParamSpec, TypeVarTuple
import contextlib as ctx
import functools as ft
import textwrap
import itertools as it
import os
from enum import Enum, auto
from datetime import timedelta, datetime, timezone
from uuid import uuid4
from io import TextIOWrapper
import subprocess
import asyncio as aio
import inspect
import shlex

### EXTERNAL
import sublime as sb
import sublime_plugin as sbp
import sublime_lib as sbl
import regex as re
from regex import Pattern
import pydantic as pyd
import more_itertools as mi

import json
import toml
import pickle as pkl
from ruamel.yaml import YAML

### INTERNAL
from .PathRegistry import PathRegistry, PATHS
from .types import TypesMixin
from .Multiplex import Multiplex

re.DEFAULT_VERSION = re.VERSION1

ViewClass: TypeAlias = Union[sbp.ViewEventListener, sbp.TextCommand]
T = TypeVar("T")
K = TypeVar("K")
S = TypeVar("S", bound=Sequence)
F = TypeVar("F", bound=FunctionType)
P = ParamSpec("P")
R = TypeVar("R")
V = TypeVar("V", bound=ViewClass)
MetaDecorator: TypeAlias = "Callable[[Callable[P, R]], Callable[P, R]]"
ViewPropertyDecorator: TypeAlias = "Callable[[Callable[[V], R]], Callable[[V], R]]"

Rest = TypeVarTuple("Rest")

WindowId: TypeAlias = TypesMixin.WindowId
ViewId: TypeAlias = TypesMixin.ViewId

NO_ESC = r"(?<![^\\]\\)(?<!\\{3})"
RGX_REF_RGX = re.compile(NO_ESC + r"\{\{\.(?P<name>[_[:lower:]][_[:lower:]\d]*)\}\}")


############
### BODY ###
############
class Utils(TypesMixin):
    """Simple static class for exporting typed utilities en-masse.

    Originally entirely copied from the `my-basis` PyPi plugin (by the same original developer 🙂).
    """

    RGXS: ClassVar[dict[str, Pattern]] = dict()
    YAML: ClassVar[YAML] = YAML(typ="safe")
    FILE_READERS: ClassVar[list[tuple[re.Pattern, Callable[[str], Any]]]] = []
    _IS_SETUP: ClassVar[bool] = False

    ST_VERSION: ClassVar[int] = int(sb.version())
    ST_PLATFORM: ClassVar[Literal["osx", "linux", "windows"]] = sb.platform()

    DEFAULT_DEBOUNCE: ClassVar[int] = 250
    _DEBOUNCE_REGISTRY: ClassVar[dict[str, int]] = defaultdict(int)

    PATHS: ClassVar[PathRegistry] = PATHS

    @classmethod
    def setup(cls, **yaml_args: Any) -> None:
        """Perform static setup of the Utils class -- should be done for you!"""
        if not cls._IS_SETUP:
            # I. Setup YAML
            cls.YAML.indent = yaml_args.get("indent", 4)
            cls.YAML.width = yaml_args.get("width", 100)
            cls.YAML.sequence_indent = yaml_args.get("sequence_indent", 100)
            cls.YAML.preserve_quotes = yaml_args.get("preserve_quotes", True)
            cls.YAML.allow_unicode = yaml_args.get("allow_unicode", True)
            cls.YAML.default_flow_style = yaml_args.get("default_flow_style", False)
            cls.YAML.sort_base_mapping_type_on_output = yaml_args.get(
                "sort_base_mapping_type_on_output", False
            )

            # II. Setup RGXS
            cls.RGXS = cls.rgx_dict(
                no_esc=NO_ESC,
                roman=r"(?i:M{1,4}|CM|C?D|D?C{1,3}|XC|X?L|L?X{1,3}|IX|I?V|V?I{1,3})",
                roman_quad=r"(?i:C{4}|X{4}|I{4})",
                glob_wildcard=NO_ESC + r"\*{1,}",
                case_split=r"\s+|(?<=\w)_(?=\w)|(?<=\p{Ll})(?=\p{Lu})|(?<=\p{Lu})(?=\p{Lu}\p{Ll})",
                newlines=r"\n+",
                punctuation=r'[\'".]+|(?<=\d),+(?=\d)',
                nonwords=r" *[^-\w\s]+ *",  # All non-whitespace breaks are underlines
                spaces=r" +",  # Spaces are just hyphens
                multihyphens=r"-{2,}",
            )

            # III. Setup file readers
            sublime_suffixes = dict(
                json=[
                    "settings",
                    "keymap",
                    "commands",
                    "menu",
                    "project",
                    "workspace",
                    "color-scheme",
                    "completions",
                    "theme",
                    "build",
                ],
                yaml=["syntax"],
                # xml=['snippet'],
            )
            _suffixes = {
                k: cls.multi_rgx(*v, pre="sublime-")
                for k, v in sublime_suffixes.items()
            }
            cls.FILE_READERS = cls.rgx_array(
                (rf"ya?ml|{_suffixes['yaml']}", cls.YAML.load),
                (rf"json|{_suffixes['json']}", json.loads),
                (r"to?ml", toml.loads),
                (r"pkl|pickle", lambda raw: pkl.loads(raw.encode())),
                # (rf'xml|{_suffixes["xml"]}', xml_parse),
            )

            cls._IS_SETUP = True

    @classmethod
    def posix(cls, val: int | float | datetime | None = None) -> datetime:
        """Convert a timestamp or datetime to UTC datetime.

        Args:
            val: Unix timestamp (int/float), datetime object, or None for current time.
        Returns:
            Timezone-aware datetime in UTC.
        """
        if val is None:
            return datetime.now(timezone.utc)
        elif isinstance(val, datetime):
            return val.astimezone(timezone.utc)
        else:
            return datetime.fromtimestamp(val, timezone.utc)

    @classmethod
    def posix_since(cls, val: int | float | datetime | None = None) -> timedelta:
        """Calculate time elapsed since a given timestamp.

        Args:
            val: Unix timestamp (int/float), datetime object, or None.
        Returns:
            Timedelta representing elapsed time, or zero if val is falsy.
        """
        if not val:
            return timedelta(0)
        else:
            return cls.posix() - cls.posix(val)

    @classmethod
    def milliseconds(cls, val: int | float | datetime | timedelta | None = None) -> int:
        """Convert a timedelta or datetime to milliseconds."""
        if val is None:
            val = cls.posix()

        if isinstance(val, timedelta):
            return round(val.total_seconds() * 1000)
        elif isinstance(val, datetime):
            return round(val.timestamp() * 1000)
        else:
            return int((val * 1000) if val < 10 else val)

    @classmethod
    def _clean_shell_args(
        cls, args: tuple[str | Iterable[str], ...], kwargs: dict[str, Any]
    ) -> Generator[str]:
        """Clean and flatten the given shell arguments."""
        for arg in mi.collapse(args, base_type=str, levels=1):
            yield from filter(bool, shlex.split(str(arg).strip()))
        for key, val in kwargs.items():
            if not key.startswith("-"):
                key = f"-{key}" if len(key) == 1 else f"--{key}"

            if isinstance(val, bool) and val is True:
                yield key
            elif isinstance(val, str):
                yield from (key, val)
            elif isinstance(val, Iterable):
                yield from mi.flatten((key, str(v)) for v in val)
            else:
                yield from (key, str(val))

    @staticmethod
    def ex(
        *args: str | list[str],
        cwd: str | Path | None = None,
        **kwargs: Any,
    ) -> str | None:
        """Execute the given command as a shell-interpreted subprocess.

        Args:
            *args: Command and arguments to execute. Can be multiple strings or lists of strings.
            cwd: Optional working directory to execute the command in.
            **kwargs: Additional keyword arguments that are parsed into command line options.
        """
        with ctx.suppress(Exception):
            result = subprocess.run(
                shlex.join(Utils._clean_shell_args(args, kwargs)),
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
            )
            if result.returncode == 0:
                return (result.stdout or result.stderr).strip("\n").rstrip(" ")
        return None

    @classmethod
    def execute(cls, *args: str | list[str], **kwargs: Any) -> str | None:
        """Execute the given command as a shell-interpreted subprocess."""
        return cls.ex(*args, **kwargs)

    @staticmethod
    async def exa(
        *args: str | Iterable[str],
        cwd: str | Path | None = None,
        **kwargs: Any,
    ) -> str | None:
        """Execute the given command as a shell-interpreted subprocess.

        Args:
            *args: Command and arguments to execute. Can be multiple strings or lists of strings.
            cwd: Optional working directory to execute the command in.
            **kwargs: Additional keyword arguments that are parsed into command line options.
        """
        with ctx.suppress(Exception):
            proc = await aio.create_subprocess_shell(
                shlex.join(Utils._clean_shell_args(args, kwargs)),
                stdout=aio.subprocess.PIPE,
                stderr=aio.subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return (stdout.decode() or stderr.decode()).strip("\n").rstrip(" ")
        return None

    @classmethod
    async def execute_async(cls, *args: str, **kwargs: Any) -> str | None:
        """Execute the given command as a shell-interpreted subprocess."""
        return await cls.exa(*args, **kwargs)

    @classmethod
    def rgx_dict(
        cls,
        compile_function: Callable[[str], Pattern[str]] = re.compile,
        sep: str = r"",
        **kwargs: str | Pattern[str] | Iterable[str],
    ) -> dict[str, Pattern[str]]:
        """Compile the expression strings in the given dictionary, mapping names to Patterns.

        Args:
            compile_function: Function to compile patterns (default: re.compile).
            sep: If any values in the expressions dict are lists of strings, join them with this.
            **kwargs: A mapping of string names to regular expressions (compiled or otherwise).
        Returns:
            The expressions mapping with all values now compiled.
        """
        ret = {}
        try:
            for key, val in kwargs.items():
                if isinstance(val, Pattern):
                    ret[key] = kwargs[key] = val
                    continue
                elif not isinstance(val, str):
                    val = kwargs[key] = sep.join(val)

                for match in list(RGX_REF_RGX.finditer(val)):
                    name = match["name"]
                    assert name in ret, (
                        f"Referenced non-existent group {name} in r'{val}'"
                    )
                    val = val.replace(match[0], ret[name].pattern)
                ret[key] = compile_function(val)
        except re.error as e:
            if not (key := next((k for k in kwargs.keys() if k not in ret), None)):
                raise ValueError(f"Unknown regex compilation error: {e}.") from e
            cls._debug_rgx_dict(e, key, str(kwargs[key]))

        return ret

    @classmethod
    def safe_compile(
        cls, key: str, expr: str, fn: Callable[[str], Pattern[str]]
    ) -> Pattern[str]:
        """Safely compile a regex pattern, returning None if it fails.

        Args:
            key: Name of the regex pattern (for error messages).
            expr: Regular expression to compile.
            fn: Function to compile the pattern (e.g. re.compile).
        Returns:
            Compiled regex pattern, or None if compilation fails.
        """
        try:
            ret = fn(expr)
        except re.error as e:
            print("RGX COMPILATION ERROR")
            cls._debug_rgx_dict(e, key, expr)
            ret = fn(r"ERROR")
        return ret

    @classmethod
    def _debug_rgx_dict(
        cls, e: re.error, key: str, pattern: str | Pattern[str]
    ) -> None:
        if not isinstance(pattern, str):
            pattern = pattern.pattern
        pos = getattr(e, "pos", -1)
        msg = getattr(e, "msg", "[NO MESSAGE FOUND?]").replace("\n", " ")
        row, _ = getattr(e, "lineno", 1) - 1, getattr(e, "colno")

        preamble = f'Invalid Regular Expression "{key}"'
        if pos == -1:
            out = [f"{preamble} = r'{pattern}'", f"ERROR: {e}"]
        elif row == 0:
            offset = len("ValueError: ") + len(preamble) + len("= r'") + pos
            out = [
                f"{preamble} = r'{pattern}'",
                f'{f"ERROR @ {pos} --> ":>{offset}}^ <-- ERROR: "{msg}"',
            ]
        else:
            lines = pattern.splitlines()
            if row < len(lines):
                lines.insert(
                    row + 1,
                    f"{'ERROR -->' if pos > 9 else '':>{pos}}^ <-- ERROR",
                )
            out = [f"{preamble} = r'''", *lines, "'''"]

        print(len(out))
        raise ValueError("\n".join(out).strip()) from e

    @classmethod
    def rgx_definitions(cls, groups: dict[str, str]) -> str:
        """Format a dictionary of named regex patterns into a `(?(DEFINE)...)` group."""
        if not groups:
            return ""
        return "".join(
            [r"(?(DEFINE)", *(rf"(?P<{key}>{val})" for key, val in groups.items()), ")"]
        )

    @classmethod
    def rgx_array(cls, *args: tuple[str | Pattern, T]) -> list[tuple[Pattern, T]]:
        """Compile the expressions in a list of two-tuples, effectively mapping Patterns to strings.

        Args:
            array: Iterable of (pattern, replacement) tuples.
            *args: Additional (pattern, replacement) tuples to include.
            compile_function: Function to compile patterns (default: re.compile).
        Returns:
            List of (compiled_pattern, replacement) tuples.
        """
        ret = []
        for key, val in args:
            if not isinstance(key, Pattern):
                key = re.compile(key)
            ret.append((key, val))
        return ret

    @classmethod
    def multi_rgx(
        cls,
        *expressions: str | list[str],
        branching: bool = False,
        sep: str = r" ?",
        pre: str = "",
        suf: str = "",
    ) -> str:
        """Combine expression clauses into a single alternating group that matches any of them.

        Args:
            *expressions: Regex patterns to be combined.
            sep: Separator for joining list patterns (default: ` ?`).
            pre: Prefix to add before combined pattern (default: empty).
            suf: Suffix to add after combined pattern (default: empty).
            branching: If True, use branching group (resets group names b/w branches)
        Returns:
            Combined regex pattern in group format `(?|...)` or `(?:...)`.
        """
        parts = [
            (expr if isinstance(expr, str) else sep.join(expr)) for expr in expressions
        ]
        contents = r"|".join(parts)
        start = "?|" if branching else "?:"
        return rf"{pre}({start}{contents}){suf}"

    @classmethod
    def define_rgx(cls, **kwargs: str) -> str:
        """Define a regex pattern with named capture groups.

        Args:
            **kwargs: A map from group names to raw, unwrapped expresisons.
        Returns:
            A `(?(DEFINE)...)` expression ready to be concatenated to another.
        """
        if not kwargs:
            return ""
        return "".join(
            [
                r"(?(DEFINE)",
                *(rf"(?P<{name}>{expr})" for name, expr in kwargs.items()),
                r")",
            ]
        )

    @classmethod
    def clean_rgx_match(
        cls, match: re.Match | None
    ) -> tuple[dict[str, str], dict[str, list[str]]]:
        """Normalize the structure and contents of a given match w/ repeated captures."""
        if match is None:
            return defaultdict(str), defaultdict(list)

        captures = defaultdict(
            list,
            {
                k: list(filter(bool, map(str.strip, v)))
                for k, v in match.capturesdict().items()
                if v
            },
        )
        groups = defaultdict(lambda: "", {k: v[-1] for k, v in captures.items() if v})
        return groups, captures

    @classmethod
    def rgx_fullsplit(
        cls, rgx: re.Pattern, text: str, collapse: bool = False
    ) -> tuple[list[str], list[str]]:
        """Split the given text into sections based on the given regex."""
        sections, delims = [], []
        if matches := list(rgx.finditer(text)):
            xp = 0
            for x0, x1 in (m.span() for m in matches):
                sections.append(text[xp:x0])
                delims.append(text[x0:x1])
                xp = x1
            sections.append(text[xp:])
        else:
            sections = [text]

        if sections:
            delims.insert(0, "")

            # If requested, collapse any empty sections into longer delimiters
            if collapse:
                cls._collapse_empty_sections(delims, sections)
        return delims, sections

    @staticmethod
    def _collapse_empty_sections(delims: list[str], sections: list[str]) -> None:
        """Remove any empty sections in the given delimited fullsplit(). Modifies arguments.

        Args:
            delims: List of delimiters.
            sections: List of sections.
        """
        empty_idxs = list(mi.locate(sections, lambda x: len(x) == 0))
        for i in reversed(empty_idxs):
            if i == len(sections) - 1:
                target = delims if i - 1 in empty_idxs else sections
                target[i - 1] += delims[i]
            else:
                delims[i + 1] = delims[i] + delims[i + 1]
            delims.pop(i)
            sections.pop(i)

    ROMAN_ARR: ClassVar[str] = "MDCLXVI"
    ROMAN_MAP: ClassVar[dict[str, int]] = dict(
        M=1000, D=500, C=100, L=50, X=10, V=5, I=1
    )

    @classmethod
    def decimal_to_roman(cls, decimal: int) -> str:
        """Convert a decimal number to its Roman numeral representation.

        Only supports numbers up to 3999 (MMMCMXCIX).
        """
        assert decimal <= 3999, (
            f"Decimal {decimal} too large for Roman numeral form (max 3999)."
        )
        ans = ""
        for char, val in cls.ROMAN_MAP.items():
            while decimal >= val:
                ans += char
                decimal -= val

            if decimal == 0:
                break

        # Fix quads of tens-places (e.g. IIII -> IV, XXXX -> XL, CCCC -> CD)
        for match in reversed(list(cls.RGXS["roman_quad"].finditer(ans))):
            char = match[0][0]
            d_idx = cls.ROMAN_ARR.index(char)
            x0, x1 = match.span()
            half = cls.ROMAN_ARR[d_idx - 1]
            if x0 > 0 and ans[x0 - 1] == half:
                ans = ans[: x0 - 1] + char + cls.ROMAN_ARR[d_idx - 2] + ans[x1:]
            else:
                ans = ans[:x0] + char + half + ans[x1:]

        return ans

    @classmethod
    def roman_to_decimal(cls, roman: str) -> int:
        """Convert a Roman numeral string to its decimal representation.

        Only supports valid Roman numeral strings up to MMMCMXCIX (3999).
        Invalid strings will return 0.
        """
        ans = 0
        last_index = 0
        for match in cls.RGXS["roman"].finditer(roman.upper()):
            if match.start() != last_index:
                return 0
            else:
                last_index = match.end()

            v = [cls.ROMAN_MAP[char] for char in match[0]]
            n_unique = len(set(v))
            if n_unique == 2:
                mod = v[0] * (-1 if v[1] > v[0] else 1)
                main = v[1] * (len(v) - 1)
                ans += main + mod
            elif n_unique == 1:
                ans += v[0] * len(v)
            else:
                return 0
        if last_index != len(roman):
            return 0

        return ans

    @staticmethod
    @ctx.contextmanager
    def debug_fence(
        content: Any,
        mark: str = "-",
        width: int = 128,
        indent: int = 0,
    ) -> Generator:
        """Context manager for printing debug information with a clear visual fence."""
        if indent:
            width -= indent
            pre = " " * indent
        else:
            pre = ""
        print(f"{pre}{mark * width}\n{pre}{' ' + str(content) + ' ':{mark}^{width}}")
        yield
        print(f"{pre}{mark * width}\n")

    @staticmethod
    def _multiprint_data(
        data: Collection[tuple | pyd.BaseModel | dict]
        | pyd.BaseModel
        | dict
        | Any
        | None,
        shorten: bool = False,
        depth: int = 0,
    ) -> Iterable[str]:
        _in = "\t" * depth
        if data is None:
            return

        # I. Series
        elif isinstance(data, str):
            yield f"{_in}{textwrap.shorten(data, 64, placeholder='...')}"
            return
        elif isinstance(data, (set, Sequence)):
            if len(str(data)) < 32:
                yield f"{_in}{data}"
                return

            for item in data:
                for child_line in Utils._multiprint_data(item, shorten, depth + 1):
                    if (
                        mi.ilen(it.takewhile(lambda s: s == "\t", child_line))
                        == depth + 1
                    ):
                        yield f"{_in}- {child_line.strip()}"
                    else:
                        yield f"  {child_line}"

        # II. Mappings
        elif isinstance(data, (dict, pyd.BaseModel)):
            if isinstance(data, pyd.BaseModel):
                data = data.model_dump(exclude_defaults=True)

            if len(str(data)) < 32:
                yield f"{_in}{data}"
                return

            for key, val in data.items():
                children = list(Utils._multiprint_data(val, shorten, depth + 1))
                if len(children) == 1:
                    yield f"{_in}{key}: {children[0].strip()}"
                else:
                    yield f"{_in}{key}:"
                    yield from children

        # III. All Others
        elif isinstance(data, type):
            yield f"{_in}{data.__name__}"
        else:
            yield f"{_in}{data}"

    @classmethod
    def multiprint(
        cls,
        *items: Any,
        title: str = "",
        lines: Iterable[str] | None = None,
        data: dict | pyd.BaseModel | set | Sequence | None = None,
        indent: int = 0,
        indent_range: tuple[int, int] = (0, 0),
        shorten: bool = False,
        quiet: bool = False,
        margins: tuple[int, int] = (0, 1),
        **kwargs: Any,
    ) -> str:
        """Flexibly print multiple lines with a few convenient features for plaintext formatting.

        Args:
            *items: Items to print after being converted to strings.
            title: Title line(s) to print before any indented content. Sets indent to 4 if unset.
            lines: Additional lines to print (in addition to the items), as an iterable of strings.
            data: Additional key-value pairs to print as "key: value" lines after the items.
            indent: Number of spaces to indent each line by.
            indent_range: Optional subset of line indices to apply the indent to.
            shorten: If true, apply some basic shortening techniques to the output.
            quiet: Do not print anything to stdout, just return the formatted string.
            margins: Number of newlines to print before and after the content.
            **kwargs: Additional keyword arguments to pass to `print()`.
        Returns:
            The constructed multiline string.
        """
        # I. Preprocess items into lines
        lines = list(
            mi.flatten(
                map(
                    str.splitlines,
                    it.chain(
                        lines or [],
                        map(str, items),
                        cls._multiprint_data(data, shorten),
                    ),
                )
            )
        )

        # II. Handle title lines, which are merely shorthand for indented lines at the top
        if title:
            indent = indent or 4
            indent_range = (indent_range[0] + 1, indent_range[1])
            lines.insert(0, title)

        # III. Handle indents, which can apply to all or just some of the output
        if indent:
            prefix = " " * indent
            for i in range(indent_range[0], (indent_range[1] or len(lines))):
                lines[i] = f"{prefix}{lines[i]}"

        # IV. Join the lines into a single result, and optionally print it to stdout if requested
        ret = ("\n" * margins[0]) + "\n".join(lines) + ("\n" * margins[1])
        if not quiet:
            print(ret, **kwargs)
        return ret

    @overload
    @classmethod
    def debounced(cls, /, fn: Callable[P, Any]) -> Callable[P, None]: ...

    @overload
    @classmethod
    def debounced(
        cls, /, *, delta: int | float | timedelta = DEFAULT_DEBOUNCE
    ) -> Callable[[Callable[P, Any]], Callable[P, None]]: ...

    @classmethod
    def debounced(
        cls,
        /,
        fn: Callable[P, Any] | None = None,
        *,
        delta: int | float | timedelta = DEFAULT_DEBOUNCE,
    ) -> Callable[[Callable[P, Any]], Callable[P, None]] | Callable[P, None]:
        """A decorator which debounces the calls to a function. Adapted from LSP.

        To "debounce" calls to an endpoint means to add a short delay, during which any repeated
        calls merely reset the delay timer rather than executing the function for a second time.

        Note that the return value of the function will be discarded, so it only makes sense to use
        this decorator for functions that return None.
        The function will run on Sublime's main thread.

        Args:
            fn: The function to debounce. If not provided, the decorator will return a nested
                decorator instead.
            delta: Time to debounce calls for, in milliseconds or as a timedelta.
        Returns:
            The wrapped function OR a nested decorator prepared to wrap the function, depending on
            whether a function is passed in explicitly.
        """
        delta = cls.milliseconds(delta)

        uid = uuid4().hex
        if fn is not None:
            return cls._debounce_factory(uid, fn, delta)
        else:
            return lambda _fn: cls._debounce_factory(uid, _fn, delta)

    @classmethod
    def _debounce_factory(
        cls, uid: str, fn: Callable[P, Any], delta: int
    ) -> Callable[P, None]:
        """Construct a wrapper for the given function -- see debounce() for details."""
        reg = cls._DEBOUNCE_REGISTRY

        @ft.wraps(fn)
        def _wrapped(*args: P.args, **kwargs: P.kwargs) -> None:
            """Runs every time the class is called."""

            def _check() -> None:
                """Utility callback that can be delayed."""
                _now = cls.milliseconds()
                _tt = reg[uid]
                if _tt > _now:
                    sb.set_timeout(_check, _tt - _now)
                else:
                    reg[uid] = 0
                    fn(*args, **kwargs)

            now = cls.milliseconds()
            if reg[uid] == 0:
                sb.set_timeout(_check, delta)
            reg[uid] = now + delta

        return _wrapped

    @classmethod
    def sorted_insert(
        cls, array: MutableSequence[T], item: T, key: Callable[[T], Any] = lambda x: x
    ) -> int:
        """Insert an item into a list, keeping it sorted according to the given key function."""
        new_key = key(item)
        index = mi.first(
            mi.locate(array, lambda old: key(old) > new_key), default=len(array)
        )
        array.insert(index, item)
        return index

    @classmethod
    def groupby(
        cls,
        iterable: Iterable[T],
        key: int | str | Callable[[T], K],
        drop: bool = False,
        keys: type[K] | None = None,
    ) -> Iterable[tuple[K, list[T]]]:
        """Group the items in the given iterable by the given key function."""
        if isinstance(key, int):
            pred = lambda item: item[key]  # type: ignore
        elif isinstance(key, str):
            pred = lambda item: getattr(item, key)
        else:
            pred = key

        _iter = iter(iterable)
        if drop:
            _iter = filter(lambda item: bool(pred(item)), _iter)
        _iter = sorted(iterable, key=pred)  # type: ignore

        yield from ((key, list(items)) for key, items in it.groupby(_iter, key=pred))

    @classmethod
    def indexof(cls, iterable: Sequence[T], *preds: Callable[[T], bool] | T) -> int:
        """Return the first index in the given iterable that satisfies the predicate."""
        _preds = tuple(
            (
                pred
                if (callable(pred) and isinstance(pred, FunctionType))
                else pred.__eq__
            )
            for pred in preds
        )
        uni_pred = lambda item: any(fn(item) for fn in _preds)
        return mi.first(mi.locate(iterable, uni_pred), default=-1)

    @classmethod
    def locate(cls, seq: Sequence[T], pred: Callable[[T], bool]) -> tuple[int, T]:
        """Return the object+index in the given seq that satisfies the predicate.

        Args:
            seq: seq to search through.
            pred: Predicate function to apply to each item.
            default: Default index to return if no item satisfies the predicate (default: -1).
        """
        index = cls.indexof(seq, pred)
        assert index != -1, "No item found matching predicate."
        return index, seq[index]

    @classmethod
    def pop_index(cls, sequence: list[T], index: int) -> list[T]:
        """Pop the item at the given index from the sequence, returning a new sequence."""
        assert 0 <= index < len(sequence), (
            f"Index {index} out of bounds for sequence of length {len(sequence)}."
        )
        return sequence[:index] + sequence[index + 1 :]

    @staticmethod
    def clear_cached_properties(inst: object, *properties: str) -> None:
        """Clear cached properties from an object instance.

        If no properties specified, clears all properties listed in instance's
        CACHED_PROPERTIES attribute.

        Args:
            inst: Object instance to clear cached properties from.
            *properties: Property names to clear. If empty, uses inst.CACHED_PROPERTIES.
        """
        if not properties and hasattr(inst, "CACHED_PROPERTIES"):
            properties = tuple(getattr(inst, "CACHED_PROPERTIES"))

        for prop in properties:
            if prop in inst.__dict__:
                del inst.__dict__[prop]

    @classmethod
    def plural(
        cls, count: int | float, singular: str, plural: str | None = None
    ) -> str:
        """Return the singular or plural form of a word based on the given count."""
        return singular if count == 1 else (plural or singular + "s")

    # -------
    # WRITING
    # -------
    ViewPosition: TypeAlias = "sb.Region | int | tuple[int, ...]"

    class Write(NamedTuple):
        """A simple container for batching writes to a view, used by `batch_write()` especially."""

        pos: Utils.ViewPosition
        val: Any

        def __lt__(self, other: object) -> bool:
            return isinstance(other, Utils.Write) and self.region < other.region

        @property
        def region(self) -> sb.Region:
            """The coerced SublimeText region of this tuple."""
            pos = self.pos
            if isinstance(pos, int):
                return sb.Region(pos, pos)
            elif isinstance(pos, tuple):
                assert len(pos) == 2, (
                    f"Expected a tuple of two integers, got {len(pos)}-tuple."
                )
                return sb.Region(*sorted(pos))
            else:
                assert isinstance(pos, sb.Region), (
                    f"Expected pos to be an int, a 2-tuple of ints, or a Region, got {type(pos)}."
                )
                return sb.Region(pos.begin(), pos.end()) if pos.a > pos.b else pos

        @property
        def points(self) -> tuple[int, int]:
            """Return the position as a tuple."""
            return self.region.to_tuple()

        @property
        def start(self) -> int:
            """The start position (in characters) of the region."""
            return self.region.a

        @property
        def end(self) -> int:
            """The end position (in characters) of the region."""
            return self.region.b

        @property
        def text(self) -> str:
            """The text covered by the region."""
            return str(self.val)

        @property
        def delta(self) -> int:
            """The change in length that this write would produce."""
            return len(self.region) - len(self.text)

    Writer: TypeAlias = "Callable[[ViewPosition, Any], None]"

    @classmethod
    @ctx.contextmanager
    def batch_write(
        cls, view: sb.View, edit: sb.Edit, debug: bool = False
    ) -> Generator[Writer]:
        """Context manager for batching multiple writes to a view (in reverse position order)."""
        pending_writes: deque[Utils.Write] = deque()
        yield lambda pos, val: pending_writes.append(cls.Write(pos, val))
        last = -1
        for write in sorted(pending_writes, reverse=True):
            old_region, new_text = write.region, write.text
            old_text = view.substr(old_region)
            if old_text == new_text:
                print(f"Skipping no-op write at {old_region}.")
                continue

            if debug:
                n_lines = old_text.count("\n") + 1, new_text.count("\n") + 1
                Utils.multiprint(
                    f'"""\n{textwrap.dedent(new_text)}\n"""\n',
                    title=(
                        f"Replacing "
                        f"{n_lines[0]} lines ({len(old_region)} chars) with "
                        f"{n_lines[1]} lines ({len(new_text)} characters) "
                        f"at {old_region}:"
                    ),
                )
            assert old_region.b <= last or last == -1, (
                f"Writes are overlapping or out of order @ ({old_region.b}, {last})."
            )
            last = old_region.a
            if old_region.empty():
                view.insert(edit, old_region.a, new_text)
            else:
                view.replace(edit, old_region, new_text)

    @staticmethod
    def replace(
        string: str,
        *args: tuple[str | Pattern, str | Callable[[re.Match[str]], str]],
    ) -> str:
        """Apply multiple regex replacements sequentially to a string.

        Args:
            string: Input string to transform.
            *args: Tuples of (pattern, replacement) for sequential application.
        Returns:
            String with all replacements applied in order.
        """
        for pattern, repl in args:
            string = re.sub(pattern, repl, string)
        return string

    @classmethod
    def _clean_nonwords(cls, string: str) -> str:
        """Clean non-word characters from string using standard replacements.

        Internal method that normalizes newlines, punctuation, spaces, and hyphens.

        Args:
            string: String to clean.
        Returns:
            Cleaned string with normalized spacing and punctuation.
        """
        return cls.replace(
            string,
            (cls.RGXS["newlines"], " "),
            (cls.RGXS["punctuation"], ""),
            (cls.RGXS["nonwords"], "_"),
            (cls.RGXS["spaces"], "-"),
            (cls.RGXS["multihyphens"], "-"),
        ).strip("_-")

    class TextCase(Enum):
        """Enumeration of common text case styles."""

        LOWER = auto()  #: text case
        UPPER = auto()  #: TEXT CASE
        TITLE = auto()  #: Text Case
        CAPITAL = auto()  #: Text case
        KEBAB = auto()  #: text-case
        SNAKE = auto()  #: text_case
        PASCAL = auto()  #: TextCase
        CAMEL = auto()  #: textCase

        @staticmethod
        @ft.lru_cache(maxsize=1)
        def _formatters() -> dict[str, Callable[[str], str]]:
            return dict(
                LOWER=str.lower,
                UPPER=str.upper,
                TITLE=str.title,
                CAPITAL=str.capitalize,
            )

        def apply(self, text: str, _from: Utils.TextCase | None = None) -> str:
            """Apply the formatting style to the given text."""
            if not (text := text.strip()):
                return ""
            cls = type(self)

            if _from == cls.KEBAB:
                words = text.split("-")
            elif _from == cls.SNAKE:
                words = text.split("_")
            elif _from in {cls.PASCAL, cls.CAMEL}:
                words = Utils.RGXS["case_split"].split(text)
            else:
                words = text.split()

            if words := list(filter(bool, words)):
                if _fn := self._formatters().get(self.name):
                    return _fn(" ".join(words))
                elif self in {cls.PASCAL, cls.CAMEL}:
                    words = list(map(str.capitalize, words))
                    if self == cls.CAMEL:
                        words[0] = words[0].lower()
                    return "".join(words)
                elif self in {cls.KEBAB, cls.SNAKE}:
                    sep = "-" if self == cls.KEBAB else "_"
                    return sep.join(map(str.lower, words))
                else:
                    raise ValueError(f"Unknown formatter: {self}")
            return ""

    @classmethod
    def recase(
        cls,
        string: str,
        to: TextCase | str = TextCase.SNAKE,
        _from: TextCase | str | None = None,
        clean: bool = True,
    ) -> str:
        """Fully clean and normalize a string for use as identifier or slug.

        Strips whitespace, cleans non-words, and applies case conversion.

        Args:
            string: String to clean.
            to: The new case for this string.
            _from: The current case -- specify especially if transforming from non-whitespace cases.
            clean: Whether to apply non-word cleaning to the result (default: True).
        Returns:
            Cleaned and normalized string suitable for identifiers.
        """
        if isinstance(to, str):
            to = cls.TextCase[to.upper().strip()]
        if isinstance(_from, str):
            _from = cls.TextCase[_from.upper().strip()]

        string = to.apply(string, _from=_from)
        return cls._clean_nonwords(string) if clean else string

    @classmethod
    def from_pascal(cls, string: str) -> str:
        """Convert a PascalCase string to snake_case."""
        return cls.recase(string, to=cls.TextCase.SNAKE, _from=cls.TextCase.PASCAL)

    @classmethod
    def to_pascal(cls, string: str) -> str:
        """Convert a snake_case string to PascalCase."""
        return cls.recase(string, to=cls.TextCase.PASCAL, _from=cls.TextCase.SNAKE)

    @staticmethod
    @ft.lru_cache(maxsize=1)
    def package_list() -> set[str]:
        """Collect a list of all available packages, installed or otherwise."""
        paths = {
            *filter(Path.is_dir, PATHS.pkgs.iterdir()),
            *filter(
                lambda c: c.suffix in {".sublime-package", ".zip"},
                PATHS.inst.iterdir(),
            ),
        }
        return {path.stem for path in paths}

    @staticmethod
    @ft.lru_cache(maxsize=10 * 4)
    def infer_package(context_path: Path | None = None) -> str | None:
        """Infer the package of the caller by checking the file paths of recent stack frames."""
        cls = Utils
        if context_path is not None:
            paths = {cls.normalize_path(context_path)}
        else:
            paths = {Path(frame.filename) for frame in it.islice(inspect.stack(), 1, 4)}

        packages = [
            package
            for path in paths
            if (str(path).strip("/. ") and path.exists())
            and (package := cls.infer_package_of(path))
        ]
        return packages[-1] if packages else None

    @classmethod
    def get_window(cls, window_id: WindowId) -> sb.Window | None:
        """Get a window by its ID, returning None if not found."""
        return next((w for w in sb.windows() if w.id() == window_id), None)

    @classmethod
    def open_folders(cls) -> dict[WindowId, set[Path]]:
        """A collection of all folders currently referenced by open windows."""
        ret = {}
        for window in sb.windows():
            _acc = set()
            for folder in filter(bool, window.folders()):
                path = Path(folder).expanduser()
                if path.exists():
                    _acc.add(path)
                    if path.is_symlink() and (resolved := path.resolve()).exists():
                        _acc.add(resolved)
                else:
                    print(
                        f"Warning: Folder path {path} does not exist for window {window.id()}."
                    )

            if _acc:
                ret[window.id()] = _acc

        return ret

    @classmethod
    def open_projects(cls) -> dict[str, set[Path]]:
        """A collection of all SublimeText projects referenced by one or more open windows."""
        ret = defaultdict(set)
        for window in sb.windows():
            data = window.project_data()
            file = window.project_file_name()
            if file is not None and isinstance(data, dict):
                proj_file = Path(file).expanduser()
                proj_name = proj_file.stem
                paths: list[str] = [
                    p for f in data.get("folders", []) if (p := f.get("path"))
                ]
                for raw_path in paths:
                    path = Path(raw_path).expanduser()

                    if path.exists():
                        ret[proj_name].add(path)
                    elif (rel_path := (proj_file.parent / path).resolve()).exists():
                        ret[proj_name].add(rel_path)

        return ret

    @classmethod
    def expand_symlinks(cls, *paths: Path) -> Iterator[Path]:
        """Iterate through the given paths AND their symlink origins (if any)."""
        yield from mi.flatten(
            (path, path.resolve()) if path.is_symlink() else (path,) for path in paths
        )

    @staticmethod
    @ft.lru_cache(maxsize=1)
    def package_dirs() -> list[tuple[str, Path]]:
        """Collect the directory paths of all used packages, including symlink origins.

        The order is guaranteed to put symlink targets before their origins in the list.

        Returns:
            A list of (package_name, package_path) tuples for all packages, where each package
            name may appear twice.
        """
        base_paths = [
            *filter(Path.is_dir, PATHS.pkgs.iterdir()),
            *filter(
                lambda c: c.suffix in {".sublime-package", ".zip"}, PATHS.inst.iterdir()
            ),
        ]
        ret = []
        for path in base_paths:
            ret.append((path.stem, path))
            if path.is_symlink():
                ret.append((path.stem, path.resolve()))
        return ret

    @classmethod
    def open_packages(cls) -> dict[WindowId, str]:
        """A collection of all SublimeText packages currently referenced by an open window."""
        package_dirs = cls.package_dirs()
        return {
            w_id: pkg
            for w_id, paths in cls.open_folders().items()
            if (
                pkg := next(
                    (name for name, path in package_dirs if path in paths), None
                )
            )
        }

    @classmethod
    def open_package_dirs(cls) -> list[Path]:
        """The paths to all SublimeText packages currently referenced by an open window."""
        package_dirs = cls.package_dirs()
        return [
            path
            for package in set(cls.open_packages().values())
            if (
                path := next(
                    (_pth for _pkg, _pth in package_dirs if _pkg == package), None
                )
            )
        ]

    @staticmethod
    @ft.lru_cache(2**8)
    def infer_package_of(path: Path) -> str | None:
        """Infer the package of a given path by checking which directory it falls under.

        Accounts for softlinked package directories.
        """
        cls = Utils
        package_dirs = cls.package_dirs()
        return next(
            (
                name
                for name, pkg_path in package_dirs
                if cls.is_relative_to(path, pkg_path)
            ),
            None,
        )

    @staticmethod
    def path(path: str | Path) -> Path:
        """Coerce a string path to a Path object, normalizing separators and redundant parts."""
        return Path(path).expanduser()

    @classmethod
    def qualify_resource_names(cls, *targets: str) -> list[str]:
        """Expand out the given resource paths into fully qualified versions."""
        instances = mi.flatten(map(sbl.ResourcePath.glob_resources, targets))
        return list(mi.unique_everseen(map(str, instances)))

    @classmethod
    def load_resources(cls, *targets: str | Path) -> dict[str, str]:
        """Load the text of a resource from disk or from a SublimeText package."""
        return {
            fqrn: sb.load_resource(fqrn)
            for fqrn in cls.qualify_resource_names(*map(str, targets))
        }

    @classmethod
    def window_folders(cls, window: sb.Window | None = None) -> list[Path]:
        """Return the folders of the given window as Paths."""
        window = window or sb.active_window()
        return [cls.path(folder) for folder in window.folders()]

    @classmethod
    def normalize_path(cls, path: str | Path, window: sb.Window | None = None) -> Path:
        """Normalize non-absolute paths by searching Sublime & project directories."""
        path = cls.path(path)
        # I. Handle environment variables in the first position
        count = 0
        while path.parts[0].startswith("$"):
            env_val = os.getenv(path.parts[0].lstrip("$"), "")
            assert env_val, (
                f"Environment variable {path.parts[0]} not found for path {path}."
            )
            path = Path(env_val, *path.parts[1:]).expanduser()
            count += 1
            if count > 10:
                raise ValueError(
                    f"Possible infinite loop while resolving environment variables in path {path}."
                )

        # I. Handle absolute & empty paths
        if path.is_absolute() or path.parts in (tuple(), (".",)):
            return path

        # II. Handle mainline resources
        parts = path.parts
        if (i := cls.indexof(parts, "Packages")) != -1:
            return Path(PATHS.pkgs, *parts[i + 1 :])
        elif (i := cls.indexof(parts, "Installed Packages")) != -1:
            return Path(PATHS.inst, *parts[i + 1 :])
        elif (i := cls.indexof(parts, "Package Storage")) != -1:
            return Path(PATHS.data, *parts[i + 1 :])
        elif (i := cls.indexof(parts, "Cache")) != -1:
            return Path(PATHS.cache, *parts[i + 1 :])

        # III. Handle packages lacking the proper prefix
        if (i := cls.indexof(parts, *cls.package_list())) != -1:
            return Path(PATHS.pkgs, *parts[i:])

        # IV. Handle paths relative to open folders in the current window
        folders = cls.window_folders(window)
        if (i := cls.indexof(parts, *(f.name for f in folders))) != -1:
            return Path(folders[i], *parts[i + 1 :])
        else:
            return path

    @classmethod
    def is_relative_to(cls, child: Path | str, parent: Path | str) -> bool:
        """Naively check if the child is relative to the proposed parent."""
        return str(child).startswith(str(parent))

    @classmethod
    def relativize(cls, path: Path, *parents: Path | str) -> Path | None:
        """Relativize the given path to the first matching parent, if possible."""
        return next(
            (
                path.relative_to(parent)
                for parent in map(cls.path, parents)
                if cls.is_relative_to(path, parent)
            ),
            None,
        )

    @classmethod
    def path_to_resource(cls, path: str | Path) -> str | None:
        """Convert a filesystem path to a Sublime resource path, if possible."""
        path = cls.normalize_path(path)
        if _p := cls.relativize(path, PATHS.pkgs, PATHS.inst):
            return str("Packages" / _p)
        elif _p := cls.relativize(path, PATHS.cache):
            return str("Cache" / _p)
        return None

    @classmethod
    def is_valid_path(cls, path: str | Path | None) -> bool:
        """Check if the given path exists and is not just whitespace or dots."""
        if not path:
            return False
        path = Path(path)
        return bool(path.exists() and str(path).strip("./ "))

    @classmethod
    def read_file(cls, file: str | Path, expect_one: bool = False) -> tuple[str, str]:
        """Read the text of a file from disk or from a SublimeText package."""
        # I. Check if we've been given raw text and handle that immediately
        if isinstance(file, str):
            if "\n" in file or len(file) > 256:
                return "", file
        file = cls.path(file)

        if file.is_absolute() and file.exists():
            return "", file.read_text()

        # II. Load SublimeText resources, whose paths aren't necessarily literal
        if (res := cls.path_to_resource(file)) and (texts := cls.load_resources(res)):
            if len(texts) > 1 and expect_one:
                raise ValueError(f"Found more than one valid {res}: {texts}.")
            return mi.first(texts.items())

        # III. Otherwise, try to read from disk
        if file.is_absolute():
            assert file.exists(), f"File {file} does not exist on disk."
            assert file.is_file(), f"File {file} is not a valid file on disk."
            return "", file.read_text()

        raise ValueError(f"Could not resolve `{file}` as a path nor resource.")

    @classmethod
    def from_file(
        cls,
        file: pyd.FilePath | str,
        filetype: Literal["yaml", "json", "toml", "pickle", "text"] | None = None,
        expect_one: bool = False,
    ) -> dict | list:
        """Load a YAML, JSON, TOML, or pickle file on disk or in a SublimeText package.

        Args:
            file: Path to the file to load, or raw YAML string/bytes.
            filetype: Explicit filetype to use for loading (e.g. 'yaml', 'json', 'toml', 'pickle').
                      If None, will infer from file suffix.
            expect_one: If True, log a warning if more than one resource is found.
        Returns:
            Loaded and cast data from the file/string.
        """
        filetypes: set[str]
        if filetype:
            filetypes = set(filetype.strip(". ").split("."))
        elif suffixes := Path(file).suffixes:
            filetypes = {suffix.strip(".").lower() for suffix in suffixes}
        else:
            raise ValueError(f"Could not infer filetype from {file}.")

        _, raw = cls.read_file(file, expect_one)
        reader = next(
            (
                reader
                for rgx, reader in cls.FILE_READERS
                if any(rgx.fullmatch(_ft) for _ft in filetypes)
            ),
            None,
        )
        if reader is None:
            raise ValueError(f"Unsupported file type(s): {', '.join(filetypes)}.")

        data = reader(raw)
        if data is None:
            return dict()
        elif not isinstance(data, (dict, list)):
            data = dict(data=data)
        return data

    @classmethod
    def log_to_disk(cls, target: bool | Path = True) -> pyd.FilePath | None:
        """Control whether all Sublime Text logging is also routed to a local file.

        Args:
            target: If True, logs will be written to a default file in the current directory.
                    If a string or Path is provided, logs will be written to that file.
                    If False, disk logging will be disabled.
                    If None, logging behavior is toggled.
            fmt: Format string for log messages.
            clear: If True, clears the log file if it already exists.
            level: Logging level to set for the logger.
        Returns:
            The path to the log file if logging is enabled, or None if disabled.
        """
        name = "log_to_disk"

        # I. Exit early if we're disabling logging or it's already enabled
        if not target:
            Multiplex.remove(name)
            return
        elif existing := Multiplex.get(name):
            assert isinstance(existing, TextIOWrapper), (
                f"Expected existing log stream to be a file-like object, got {type(existing)}."
            )
            return Path(str(existing.name))

        # II. Normalize target path
        if target is True:
            target = PATHS.console
        elif isinstance(target, str):
            target = Path(target).expanduser().resolve()

        # III. Prepare target file by making sure it's empty
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("")

        # IV. Register new stream, automatically wrapping STDOUT if it isn't already
        Multiplex.add(name, target.open("a"), mode="WRAPPER")
        return target


ut = utils = Utils
Utils.setup()
