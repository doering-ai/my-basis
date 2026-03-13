############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from collections import defaultdict, deque
from collections.abc import Callable, Iterator, MutableSequence
from pathlib import Path
from types import FunctionType
from typing import ClassVar, TypeVar, Any, Literal, Union, NamedTuple
from typing_extensions import TypeAlias, ParamSpec
import contextlib as ctx
import functools as ft
import time
import warnings
import textwrap

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

re.DEFAULT_VERSION = re.VERSION1

ViewClass: TypeAlias = Union[sbp.ViewEventListener, sbp.TextCommand]
T = TypeVar('T')
F = TypeVar('F', bound=FunctionType)
P = ParamSpec('P')
R = TypeVar('R')
V = TypeVar('V', bound=ViewClass)
ViewPropertyDecorator: TypeAlias = 'Callable[[Callable[[V], R]], Callable[[V], R]]'

NO_ESC = r'(?<![^\\]\\)(?<!\\{3})'
RGX_REF_RGX = re.compile(NO_ESC + r'\{\{\.(?P<name>[_[:lower:]][_[:lower:]\d]*)\}\}')


############
### BODY ###
############
class Utils(TypesMixin):
    """Simple static class for exporting typed utilities en-masse.

    Almost entirely copied from the `my-basis` PyPi plugin (by the same original developer 🙂).
    """

    RGXS: ClassVar[dict[str, Pattern]] = dict()
    YAML: ClassVar[YAML] = YAML(typ='safe')
    FILE_READERS: ClassVar[list[tuple[re.Pattern, Callable[[str], Any]]]] = []
    _IS_SETUP: ClassVar[bool] = False

    ST_VERSION: ClassVar[int] = int(sb.version())
    ST_PLATFORM: ClassVar[Literal['osx', 'linux', 'windows']] = sb.platform()

    DEBOUNCE_TIME: ClassVar[float] = 0.5

    PATHS: ClassVar[PathRegistry] = PATHS

    @classmethod
    def setup(cls, **yaml_args: Any) -> None:
        """Perform static setup of the Utils class -- should be done for you!"""
        if not cls._IS_SETUP:
            # I. Setup YAML
            cls.YAML.indent = yaml_args.get('indent', 4)
            cls.YAML.width = yaml_args.get('width', 100)
            cls.YAML.sequence_indent = yaml_args.get('sequence_indent', 100)
            cls.YAML.preserve_quotes = yaml_args.get('preserve_quotes', True)
            cls.YAML.allow_unicode = yaml_args.get('allow_unicode', True)
            cls.YAML.default_flow_style = yaml_args.get('default_flow_style', False)
            cls.YAML.sort_base_mapping_type_on_output = yaml_args.get(
                'sort_base_mapping_type_on_output', False
            )

            # II. Setup RGXS
            cls.RGXS = Utils.rgx_dict(
                no_esc=NO_ESC,
                roman=r'(?i:M{1,4}|CM|C?D|D?C{1,3}|XC|X?L|L?X{1,3}|IX|I?V|V?I{1,3})',
                roman_quad=r'(?i:C{4}|X{4}|I{4})',
                glob_wildcard=NO_ESC + r'\*{1,}',
            )

            # III. Setup file readers
            sublime_suffixes = dict(
                json=[
                    'settings',
                    'keymap',
                    'commands',
                    'menu',
                    'project',
                    'workspace',
                    'color-scheme',
                    'completions',
                    'theme',
                    'build',
                ],
                yaml=['syntax'],
                # xml=['snippet'],
            )
            _suffixes = {k: cls.multi_rgx(*v, pre='sublime-') for k, v in sublime_suffixes.items()}
            cls.FILE_READERS = Utils.rgx_array(
                (rf'ya?ml|{_suffixes["yaml"]}', cls.YAML.load),
                (rf'json|{_suffixes["json"]}', json.loads),
                (r'to?ml', toml.loads),
                (r'pkl|pickle', lambda raw: pkl.loads(raw.encode())),
                # (rf'xml|{_suffixes["xml"]}', xml_parse),
            )

            cls._IS_SETUP = True

    @staticmethod
    def path_dict(**kwargs: str | Path) -> dict[str, Path]:
        """Expand the given dictionary of paths, mapping names to Paths.

        Args:
            **kwargs: A mapping of string names to file paths (as strings or Paths).
        Returns:
            The paths mapping with all values now expanded to Paths.
        """
        return {key: Path(val).expanduser().resolve() for key, val in kwargs.items()}

    @staticmethod
    def rgx_dict(
        compile_function: Callable[[str], Pattern[str]] = re.compile,
        **kwargs: str | Pattern[str],
    ) -> dict[str, Pattern[str]]:
        """Compile the expression strings in the given dictionary, mapping names to Patterns.

        Args:
            expressions: A mapping of string names to regular expressions (compiled or otherwise).
            compile_function: Function to compile patterns (default: re.compile).
            **kwargs: Additional named patterns to include.
        Returns:
            The expressions mapping with all values now compiled.
        """
        ret = {}
        try:
            for key, val in kwargs.items():
                if isinstance(val, Pattern):
                    ret[key] = val
                else:
                    for match in list(RGX_REF_RGX.finditer(val)):
                        name = match['name']
                        assert name in ret, f"Referenced non-existent group {name} in r'{val}'"
                        val = val.replace(match[0], ret[name].pattern)
                    ret[key] = compile_function(val)
        except re.error as e:
            if not (key := next((k for k in kwargs.keys() if k not in ret), None)):
                raise ValueError(f'Unknown regex compilation error: {e}.') from e
            Utils._debug_rgx_dict(e, key, kwargs[key])

        return ret

    @staticmethod
    def safe_compile(key: str, expr: str, fn: Callable[[str], Pattern[str]]) -> Pattern[str]:
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
            print('RGX COMPILATION ERROR')
            Utils._debug_rgx_dict(e, key, expr)
            ret = fn(r'ERROR')
        return ret

    @staticmethod
    def _debug_rgx_dict(e: re.error, key: str, pattern: str | Pattern[str]) -> None:
        if not isinstance(pattern, str):
            pattern = pattern.pattern
        pos = getattr(e, 'pos', -1)
        msg = getattr(e, 'msg', '[NO MESSAGE FOUND?]').replace('\n', ' ')
        row, _ = getattr(e, 'lineno', 1) - 1, getattr(e, 'colno')

        preamble = f'Invalid Regular Expression "{key}"'
        if pos == -1:
            out = [f"{preamble} = r'{pattern}'", f'ERROR: {e}']
        elif row == 0:
            offset = len('ValueError: ') + len(preamble) + len("= r'") + pos
            out = [
                f"{preamble} = r'{pattern}'",
                f'{f"ERROR @ {pos} --> ":>{offset}}^ <-- ERROR: "{msg}"',
            ]
        else:
            lines = pattern.splitlines()
            if row < len(lines):
                lines.insert(
                    row + 1,
                    f'{"ERROR -->" if pos > 9 else "":>{pos}}^ <-- ERROR',
                )
            out = [f"{preamble} = r'''", *lines, "'''"]

        print(len(out))
        raise ValueError('\n'.join(out).strip()) from e

    @staticmethod
    def rgx_definitions(groups: dict[str, str]) -> str:
        """Format a dictionary of named regex patterns into a `(?(DEFINE)...)` group."""
        if not groups:
            return ''
        return ''.join([r'(?(DEFINE)', *(rf'(?P<{key}>{val})' for key, val in groups.items()), ')'])

    @staticmethod
    def rgx_array(*args: tuple[str | Pattern, T]) -> list[tuple[Pattern, T]]:
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

    @staticmethod
    def multi_rgx(
        *expressions: str | list[str],
        branching: bool = False,
        sep: str = r' ?',
        pre: str = '',
        suf: str = '',
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
        parts = [(expr if isinstance(expr, str) else sep.join(expr)) for expr in expressions]
        contents = r'|'.join(parts)
        start = '?|' if branching else '?:'
        return rf'{pre}({start}{contents}){suf}'

    @staticmethod
    def define_rgx(**kwargs: str) -> str:
        """Define a regex pattern with named capture groups.

        Args:
            **kwargs: A map from group names to raw, unwrapped expresisons.
        Returns:
            A `(?(DEFINE)...)` expression ready to be concatenated to another.
        """
        if not kwargs:
            return ''
        return ''.join(
            [
                r'(?(DEFINE)',
                *(rf'(?P<{name}>{expr})' for name, expr in kwargs.items()),
                r')',
            ]
        )

    @staticmethod
    def clean_rgx_match(match: re.Match | None) -> tuple[dict[str, str], dict[str, list[str]]]:
        """Normalize the structure and contents of a given match w/ repeated captures."""
        if match is None:
            return {}, {}

        captures = defaultdict(
            list,
            {
                k: list(filter(bool, map(str.strip, v)))
                for k, v in match.capturesdict().items()
                if v
            },
        )
        groups = defaultdict(str, {k: v[-1] for k, v in captures.items() if v})
        return groups, captures

    @staticmethod
    def rgx_fullsplit(
        rgx: re.Pattern, text: str, collapse: bool = False
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
            delims.insert(0, '')

            # If requested, collapse any empty sections into longer delimiters
            if collapse:
                Utils._collapse_empty_sections(delims, sections)
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

    ROMAN_ARR: ClassVar[str] = 'MDCLXVI'
    ROMAN_MAP: ClassVar[dict[str, int]] = dict(M=1000, D=500, C=100, L=50, X=10, V=5, I=1)

    @staticmethod
    def decimal_to_roman(decimal: int) -> str:
        """Convert a decimal number to its Roman numeral representation.

        Only supports numbers up to 3999 (MMMCMXCIX).
        """
        assert decimal <= 3999, f'Decimal {decimal} too large for Roman numeral form (max 3999).'
        ans = ''
        for char, val in Utils.ROMAN_MAP.items():
            while decimal >= val:
                ans += char
                decimal -= val

            if decimal == 0:
                break

        # Fix quads of tens-places (e.g. IIII -> IV, XXXX -> XL, CCCC -> CD)
        for match in reversed(list(Utils.RGXS['roman_quad'].finditer(ans))):
            char = match[0][0]
            d_idx = Utils.ROMAN_ARR.index(char)
            x0, x1 = match.span()
            half = Utils.ROMAN_ARR[d_idx - 1]
            if x0 > 0 and ans[x0 - 1] == half:
                ans = ans[: x0 - 1] + char + Utils.ROMAN_ARR[d_idx - 2] + ans[x1:]
            else:
                ans = ans[:x0] + char + half + ans[x1:]

        return ans

    @staticmethod
    def roman_to_decimal(roman: str) -> int:
        """Convert a Roman numeral string to its decimal representation.

        Only supports valid Roman numeral strings up to MMMCMXCIX (3999).
        Invalid strings will return 0.
        """
        ans = 0
        last_index = 0
        for match in Utils.RGXS['roman'].finditer(roman.upper()):
            if match.start() != last_index:
                return 0
            else:
                last_index = match.end()

            v = [Utils.ROMAN_MAP[char] for char in match[0]]
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
        mark: str = '-',
        width: int = 128,
        indent: int = 0,
    ) -> Iterator[None]:
        """Context manager for printing debug information with a clear visual fence."""
        if indent:
            width -= indent
            pre = ' ' * indent
        else:
            pre = ''
        print(f'{pre}{mark * width}\n{pre}{" " + str(content) + " ":{mark}^{width}}')
        yield
        print(f'{pre}{mark * width}\n')

    @staticmethod
    def multiprint(
        *items: Any,
        title: str = '',
        indent: int = 0,
        indent_range: tuple[int, int] = (0, 0),
        quiet: bool = False,
        margins: tuple[int, int] = (0, 1),
        **kwargs: Any,
    ) -> str:
        """Flexibly print multiple lines with a few convenient features for plaintext formatting.

        Args:
            *items: Items to print after being converted to strings.
            title: Title line(s) to print before any indented content. Sets indent to 4 if unset.
            indent: Number of spaces to indent each line by.
            indent_range: Optional subset of line indices to apply the indent to.
            quiet: Do not print anything to stdout, just return the formatted string.
            margins: Number of newlines to print before and after the content.
            **kwargs: Additional keyword arguments to pass to `print()`.
        Returns:
            The constructed multiline string.
        """
        # I. Preprocess items into lines
        lines = list(mi.flatten(map(str.splitlines, map(str, items))))

        # II. Handle title lines, which are merely shorthand for indented lines at the top
        if title:
            indent = indent or 4
            indent_range = (indent_range[0] + 1, indent_range[1])
            lines.insert(0, title)

        # III. Handle indents, which can apply to all or just some of the output
        if indent:
            prefix = ' ' * indent
            for i in range(indent_range[0], (indent_range[1] or len(lines))):
                lines[i] = f'{prefix}{lines[i]}'

        # IV. Join the lines into a single result, and optionally print it to stdout if requested
        ret = ('\n' * margins[0]) + '\n'.join(lines) + ('\n' * margins[1])
        if not quiet:
            print(ret, **kwargs)
        return ret

    @staticmethod
    def debounced(fn: Callable[P, Any]) -> Callable[P, None]:
        """A decorator which debounces the calls to a function.

        Adapted from LSP.

        Note that the return value of the function will be discarded, so it only makes sense to use
        this decorator for functions that return None. The function will run on Sublime's main
        thread.
        """

        @ft.wraps(fn)
        def _wrapped(*args: P.args, **kwargs: P.kwargs) -> None:
            def _check() -> None:
                target_time = getattr(_wrapped, '_target_time', None)
                if isinstance(target_time, float):
                    if (delay := target_time - time.monotonic()) > 0:
                        _wrapped._target_time = None  # type: ignore
                        sb.set_timeout(_check, int(delay * 1000))
                        return
                delattr(_wrapped, '_target_time')
                fn(*args, **kwargs)

            if hasattr(_wrapped, '_target_time'):
                _wrapped._target_time = time.monotonic() + Utils.DEBOUNCE_TIME  # type: ignore
                return
            _wrapped._target_time = None  # type: ignore
            sb.set_timeout(_check, int(Utils.DEBOUNCE_TIME * 1000))

        return _wrapped

    @staticmethod
    def sorted_insert(
        array: MutableSequence[T], item: T, key: Callable[[T], Any] = lambda x: x
    ) -> int:
        """Insert an item into a list, keeping it sorted according to the given key function."""
        new_key = key(item)
        index = mi.first(mi.locate(array, lambda old: key(old) > new_key), default=len(array))
        array.insert(index, item)
        return index

    ViewPosition: TypeAlias = 'sb.Region | int | tuple[int, ...]'

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
                assert len(pos) == 2, f'Expected a tuple of two integers, got {len(pos)}-tuple.'
                return sb.Region(*sorted(pos))
            else:
                assert isinstance(pos, sb.Region), (
                    f'Expected pos to be an int, a 2-tuple of ints, or a Region, got {type(pos)}.'
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

    Writer: TypeAlias = 'Callable[[ViewPosition, Any], None]'

    @classmethod
    @ctx.contextmanager
    def batch_write(cls, view: sb.View, edit: sb.Edit, debug: bool = False) -> Iterator[Writer]:
        """Context manager for batching multiple writes to a view (in reverse position order)."""
        pending_writes: deque[Utils.Write] = deque()
        yield lambda pos, val: pending_writes.append(cls.Write(pos, val))
        last = -1
        for write in sorted(pending_writes, reverse=True):
            old_region, new_text = write.region, write.text
            old_text = view.substr(old_region)
            if old_text == new_text:
                print(f'Skipping no-op write at {old_region}.')
                continue

            if debug:
                n_lines = old_text.count('\n') + 1, new_text.count('\n') + 1
                Utils.multiprint(
                    f'"""\n{textwrap.dedent(new_text)}\n"""\n',
                    title=(
                        f'Replacing '
                        f'{n_lines[0]} lines ({len(old_region)} chars) with '
                        f'{n_lines[1]} lines ({len(new_text)} characters) '
                        f'at {old_region}:'
                    ),
                )
            assert old_region.b <= last or last == -1, (
                f'Writes are overlapping or out of order @ ({old_region.b}, {last}).'
            )
            last = old_region.a
            if old_region.empty():
                view.insert(edit, old_region.a, new_text)
            else:
                view.replace(edit, old_region, new_text)

    @staticmethod
    @ft.lru_cache(maxsize=1)
    def package_list() -> set[str]:
        """Collect a list of all available packages, installed or otherwise."""
        paths = {
            *filter(Path.is_dir, PATHS.packages.iterdir()),
            *filter(
                lambda c: c.suffix in {'.sublime-package', '.zip'},
                PATHS.installed_packages.iterdir(),
            ),
        }
        return {path.stem for path in paths}

    @classmethod
    def qualify_resource_names(cls, *targets: str) -> list[str]:
        """Expand out the given resource paths into fully qualified versions."""
        instances = mi.flatten(map(sbl.ResourcePath.glob_resources, targets))
        return list(mi.unique_everseen(map(str, instances)))

    @classmethod
    def load_resources(cls, *targets: str | Path) -> dict[str, str]:
        """Load the text of a resource from disk or from a SublimeText package."""
        return {
            fqrn: sb.load_resource(fqrn) for fqrn in cls.qualify_resource_names(*map(str, targets))
        }

    @classmethod
    def try_to_relativize(cls, file: Path) -> str:
        """Try to turn this file path into a resource str."""
        if (
            pkgroot := next(
                (
                    i
                    for i, part in enumerate(file.parts)
                    if part in {'Packages', 'Installed Packages'}
                ),
                None,
            )
            is not None
        ):
            return str('Packages' / Path(*file.parts[pkgroot + 1 :]))
        elif (
            cacheroot := next((i for i, part in enumerate(file.parts) if part == 'Caches'), None)
        ) is not None:
            return str(Path(*file.parts[cacheroot:]))

        if file.is_relative_to(PATHS.packages):
            return str('Pacakges' / file.relative_to(PATHS.packages))
        elif file.is_relative_to(PATHS.packages):
            return str('Pacakges' / file.relative_to(PATHS.packages))
        elif file.is_relative_to(PATHS.cache):
            return str('Caches' / file.relative_to(sb.cache_path()))

        return ''

    @classmethod
    def read_file(cls, file: str | Path, expect_one: bool = False) -> tuple[str, str]:
        """Read the text of a file from disk or from a SublimeText package."""
        if isinstance(file, str):
            if '\n' in file:
                return '', file
            file = Path(file)
        file = file.expanduser()

        if file.is_absolute():
            if _rel := cls.try_to_relativize(file):
                file = _rel
            else:
                assert file.exists(), f'File {file} does not exist on disk.'
                assert file.is_file(), f'File {file} is not a valid file on disk.'
                return '', file.read_text()

        results = cls.load_resources(file)
        if len(results) == 0:
            raise FileNotFoundError(f'Could not find file {file} on disk or in packages.')
        elif len(results) > 1 and expect_one:
            warnings.warn(
                f'Found multiple resources matching {file} -- using first match.', stacklevel=3
            )
        return mi.first(results.items())

    @classmethod
    def from_file(
        cls,
        file: pyd.FilePath | str,
        filetype: Literal['yaml', 'json', 'toml', 'pickle', 'text'] | None = None,
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
            filetypes = set(filetype.strip('. ').split('.'))
        elif suffixes := Path(file).suffixes:
            filetypes = {suffix.strip('.').lower() for suffix in suffixes}
        else:
            raise ValueError(f'Could not infer filetype from {file}.')

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
            raise ValueError(f'Unsupported file type(s): {", ".join(filetypes)}.')

        data = reader(raw)
        if data is None:
            return dict()
        elif not isinstance(data, (dict, list)):
            data = dict(data=data)
        return data


Utils.setup()

ut = utils = Utils
