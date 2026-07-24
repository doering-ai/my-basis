############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, Annotated
from pathlib import Path
import os
import functools as ft

### EXTERNAL
import pydantic as pyd
import regex as re

### INTERNAL
from ..infra.constants import INFRA_PATHS
from ..utils import ut
from ..regex import RegexStore
from ..typing import typist
from ..types import Platform
from .Environment import env


class Convention(pyd.BaseModel):
    """A model representing a single platform's user directory conventions.

    Each field maps a directory purpose (`config`, `cache`, or `data`) to a tuple of the
    environment variable that may override it and the platform's default path.
    """

    #: The "configuration" directory, i.e. ~/.config
    config: tuple[str, str] = ('', '')

    #: The "cache" directory, i.e. ~/.cache
    cache: tuple[str, str] = ('', '')

    #: The "local" or "data" directory, i.e. ~/.local/share
    data: tuple[str, str] = ('', '')

    @ft.lru_cache(1)
    @staticmethod
    def conventions() -> dict[Platform, Convention]:
        """Load the per-platform directory conventions from the bundled YAML data file."""
        text = (INFRA_PATHS.data / 'platform-conventions.yaml').read_text()
        data = typist.from_yaml(text, dict[str, dict[str, tuple[str, str]]])

        return {
            Platform[_platform.upper()]: Convention(**_plat_data)
            for _platform, _plat_data in data.items()
        }

    def resolve(self, envvar: str, default: str) -> Path:
        """Resolve an (envvar, default) pair to a path, preferring the environment variable."""
        return ut.path(os.getenv(envvar, default))


############
### DATA ###
############
#: Regexes, mostly for identifying project directories by their tell-tale files and folders.
RGXS = RegexStore.new(
    options=RegexStore.Options(force_named_groups=True),
    branch=(
        '<|>is',
        r'^(?:[^\n\/]*\/)*',
        [
            r'\.(git|venv|eggs|npm|n[eu]xt|vercel|tox)',
            r'build|dist|node_modules|wheels|venv|pyv?env',
        ],
        r'$',
    ),
    leaf=(
        '<|>is',
        r'^(?:[^\n\/]*\/)*',
        [
            r'\.(python-version|(git)?ignore)',
            r'(Task|Make|Docker|Container)file',
            r'(uv|yarn|npm|pypi)\.lock',
            r'next-env\.d\.ts',
            r'setup\.py|requirements\.txt|pyvenv\.cfg',
            ('|:', r'', [r'package(?:-lock)?'], r'\.jso?n'),
            (
                '|:',
                r'',
                [
                    'pyproject',
                    r'mypy|pyrefly|(?:based)?pyright|ty',
                    r'ruff|cargo|mise',
                    'prek',
                ],
                r'\.to?ml',
            ),
            (
                '|:',
                r'',
                [
                    (
                        '|:',
                        r'\.',
                        ['gitlab-ci', 'github', 'plumber', 'readthedocs', 'pre-commit'],
                        r'[-\w]*',
                    ),
                ],
                r'\.ya?ml',
            ),
        ],
        r'$',
    ),
    platform=r'',
)

#: Timeout (seconds) for searches against raw patterns pulled off `RGXS` (e.g. `RGXS['leaf']`).
#: Subscripting a `RegexStore` hands back the bare compiled pattern, bypassing the store's own
#: timeout-guarded `search()`/`match()` -- so call sites that go this route must pass this
#: explicitly. Mirrors `RegexStore.REGEX_TIMEOUT` / `Buffer.REGEX_TIMEOUT`.
REGEX_TIMEOUT: float = 10.0

#: A sentinel value that communicates a failure of some kind, or an uninitialized register.
NOWHERE = Path()

Leaf, Branch = pyd.FilePath, pyd.DirectoryPath
LeafField = Annotated[Path, pyd.BeforeValidator(ut.path)]  # Files
BranchField = Annotated[Path, pyd.BeforeValidator(ut.path)]  # Directories

_PLAT: Platform = Platform.local()
_CONV: Convention = Convention.conventions()[_PLAT]


############
### BODY ###
############
class Filesystem(pyd.BaseModel):
    """A registry of file paths, mapping string names to Path objects.

    Each instance carries the platform's conventional user directories (`home`, `config`,
    `cache`, `data`) plus the workspace roots configured through environment variables like
    `$MY` and `$MY_LOCAL`. The class also collects a family of `classmethod` path utilities
    usable without any instance. A default instance is exported as `fs` (aliased `FS` and
    `PATHS`).

    Examples:
        The default instance reflects the local machine::

            >>> from pathlib import Path
            >>> from my.apis import fs
            >>> fs.home == Path.home()
            True
    """

    RGXS: ClassVar[RegexStore] = RGXS
    PATH_VARS: ClassVar[dict[str, str]] = {
        f'{key}': val for key, val in os.environ.items() if val.count('/') >= 2 and val[0] == '/'
    }

    # ---- Dynamic / Runtime ----
    plat: Platform = Platform.local()

    # ---- System ----
    home: BranchField = Path.home()
    config: BranchField = _CONV.resolve(*_CONV.config)
    cache: BranchField = _CONV.resolve(*_CONV.cache)
    data: BranchField = _CONV.resolve(*_CONV.data)

    # ---- Workspaces ----
    my: BranchField = env.path('MY', home / 'my')
    creds: BranchField = env.path('MY_CREDS', my / '.creds')
    corpus: BranchField = env.path('MY_CORPUS', my / 'corpus')

    # ---- Local ----
    local: BranchField = env.path('MY_LOCAL', home / 'local')
    logs: BranchField = env.path('MY_LOGS', local / 'logs')
    models: BranchField = env.path('MY_MODELS', local / 'models')
    metrics: BranchField = env.path('MY_METRICS', local / 'metrics')

    # -------------------
    # `.` Initial Methods
    # -------------------

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _check_for_project_root(cls, folder: pyd.DirectoryPath) -> str | None:
        """Check if the given folder contains common project root indicators."""
        leaves, branches = ut.partition(folder.iterdir(), Path.is_dir)
        # `RGXS['leaf']`/`RGXS['branch']` are raw compiled patterns (see `REGEX_TIMEOUT` above),
        # so `timeout=` must be passed explicitly here to keep this guarded against pathological
        # input -- unlike `RGXS.search(...)`, which enforces it internally.
        if match := RGXS['leaf'].search(
            '\n'.join(map(Path.as_posix, leaves)), timeout=REGEX_TIMEOUT
        ):
            return match[1]
        elif match := RGXS['branch'].search(
            '\n'.join(map(Path.as_posix, branches)), timeout=REGEX_TIMEOUT
        ):
            return match[1]
        return None

    # -------------------
    # `+` Primary Methods
    # -------------------
    @staticmethod
    @ft.lru_cache(maxsize=256)
    def compile_rgx(path: Path | str) -> re.Pattern[str]:
        """Compile a boundary-aware pattern for a non-root POSIX path.

        The match starts with `/`, `./`, or one or more `../` segments. It will not begin
        inside a URI, UNC path, or DOS drive-root path. URI, UNC, DOS/backslash, empty, and
        filesystem-root inputs are rejected rather than interpreted heuristically.

        Capture group 1 contains the literal path without its leading slash. Capture group 2
        contains one optional trailing slash.

        Args:
            path: Non-root POSIX path to escape and match literally.
        Returns:
            Compiled path pattern with the literal body and trailing slash captured.
        Raises:
            ValueError: If path is not a non-root POSIX path.
        Examples:
            Relative prefixes are part of the match but not the literal-body capture::

                >>> from my.apis import Filesystem
                >>> pattern = Filesystem.compile_rgx('/srv/app')
                >>> match = pattern.search('from ../srv/app/logs')
                >>> match[0], match[1]
                ('../srv/app/', 'srv/app')
                >>> pattern.search('file:///srv/app') is None
                True
        """
        raw = str(path)
        normalized = Path(path).as_posix()
        unsupported = (
            not raw
            or normalized in {'.', '..', '/'}
            or '\\' in raw
            or raw.startswith('//')
            or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', raw)
        )
        if unsupported:
            raise ValueError(
                'Filesystem.compile_rgx accepts non-root POSIX paths only; '
                'URI, UNC, DOS/backslash, empty, and filesystem-root inputs are unsupported.'
            )

        literal = re.escape(normalized.strip('/'))
        expr = rf'(?<![-\w/.:])(?:(?:\.\./)+|\./|/(?!/))({literal})(?![-.\w])(/?)'
        return re.compile(expr)

    # ------------------
    # `*` Public Methods
    # ------------------
    def __str__(self) -> str:
        attrs = self.model_dump()
        w = max(map(len, attrs.keys())) + 1
        return '\n'.join(
            [
                f'{self.__class__.__name__}:',
                *(f'\t{key:>{w}}: {val}' for key, val in attrs.items()),
            ]
        )

    @ft.cached_property
    def rgxs(self) -> dict[str, re.Pattern[str]]:
        """Compile patterns for every path-valued registry field.

        Non-path metadata such as `plat` is omitted.

        Returns:
            Map from path field name to its compiled literal-path pattern.
        Examples:
            Platform metadata is not a path pattern::

                >>> from my.apis import fs
                >>> 'plat' in fs.rgxs
                False
                >>> bool(fs.rgxs['home'].search(fs.home.as_posix()))
                True
        """
        return {
            name: self.compile_rgx(path)
            for name, path in reversed(self.model_dump().items())
            if isinstance(path, Path)
        }

    @classmethod
    def is_possible(cls, raw: str | Path | None) -> bool:
        """Check if the given value denotes a usable, non-trivial path.

        Args:
            raw: Path-like value to inspect.
        Returns:
            True unless the value is empty, None, or normalizes to a rootless/trivial path.
        Examples:
            Empty-ish values fail; anything that normalizes to a real shape passes::

                >>> from my.apis import Filesystem
                >>> Filesystem.is_possible('/srv/app')
                True
                >>> Filesystem.is_possible('')
                False
        """
        return bool(raw and (_p := cls.path(raw)).root and str(_p).strip('./\\ '))

    @classmethod
    def is_actual(cls, raw: str | Path | None) -> bool:
        """Check if the given path actually exists on this machine.

        Args:
            raw: Path-like value to inspect.
        Returns:
            True when the value is a possible path that exists on disk.
        Examples:
            Existence is checked after normalization::

                >>> from pathlib import Path
                >>> from my.apis import Filesystem
                >>> Filesystem.is_actual(Path.home())
                True
                >>> Filesystem.is_actual('/no/such/place')
                False
        """
        return bool(raw and cls.is_possible(path := cls.path(raw)) and path.exists())

    @classmethod
    def path(cls, raw: str | Path | None) -> Path:
        """Normalize a path -- see `ut.path()` for full documentation.

        Expands `~` and environment variables, then resolves the result to an absolute path.

        Examples:
            Relative segments are resolved lexically::

                >>> from my.apis import Filesystem
                >>> Filesystem.path('/srv/app/../logs')
                PosixPath('/srv/logs')
        """
        return ut.path(raw)

    @classmethod
    def is_relative_to(cls, child: Path | str, parent: Path | str) -> bool:
        """Check if the child path sits under the proposed parent, segment-aware.

        A convenience wrapper over `Path.is_relative_to()` that accepts strings, so sibling
        names sharing a prefix (`/srv/app2` vs `/srv/app`) are correctly kept apart.

        Args:
            child: Path to check.
            parent: Proposed parent path.
        Returns:
            Whether the child is relative to parent.
        Examples:
            Compare by whole path segments, not string prefixes::

                >>> from my.apis import Filesystem
                >>> Filesystem.is_relative_to('/srv/app/logs', '/srv/app')
                True
                >>> Filesystem.is_relative_to('/srv/app2', '/srv/app')
                False
        """
        return Path(child).is_relative_to(Path(parent))

    @classmethod
    def relativize(cls, path: Path, *ancestors: Path | str) -> Path | None:
        """Relativize the given path to the first matching parent if possible, or none otherwise.

        Args:
            path: Path to relativize, which must be absolute. Doesn't have to exist.
            *ancestors: One or more potential ancestors to check against.
        Returns:
            The same path but relative to the first matching ancestor, otherwise None.
        Examples:
            The first matching ancestor wins; non-absolute paths are refused::

                >>> from pathlib import Path
                >>> from my.apis import Filesystem
                >>> Filesystem.relativize(Path('/srv/app/logs/x.log'), '/opt', '/srv/app')
                PosixPath('logs/x.log')
                >>> Filesystem.relativize(Path('relative/x.log'), '/srv') is None
                True
        """
        if not path.is_absolute():
            return None

        return next(
            (
                path.relative_to(anc)
                for anc in map(cls.path, ancestors)
                if cls.is_relative_to(path, anc)
            ),
            None,
        )

    @classmethod
    def seek_project(cls, path: Path | None = None) -> Path | None:
        """Attempt to find the project root by looking for common indicators.

        Walks the strict ancestors of the starting directory (not the directory itself),
        stopping at the user's home directory. An ancestor counts as a project root when it
        contains a recognizable marker file (`pyproject.toml`, `Taskfile`, a lockfile, ...) or
        directory (`.git`, `node_modules`, ...).

        Args:
            path: Starting path to search from, defaulting to the working directory. If a file
                is given, its parent will be used.
        Returns:
            The first ancestor containing a project marker, or None if the walk reaches home.
        """
        path = path or Path.cwd()

        # I. Validate & normalize arguments into a single starting directory
        if path.parent.exists() and (not path.exists() or path.is_file()):
            root = path.parent
        else:
            root = path

        for ancestor in root.parents:
            print(f'Checking ancestor {ancestor}')
            if ancestor == Path.home():
                return None
            elif trigger := cls._check_for_project_root(ancestor):
                print(f'Found trigger "{trigger}" in {ancestor}')
                return ancestor
        return None

    @classmethod
    def shortpath(cls, path: str | Path | None) -> str:
        """Relativize the given path to a shorter form if possible. For casual use.

        Candidate anchors are the working directory (`.`), the home directory (`~`), and any
        absolute paths found in environment variables; unmatched paths yield the empty string.

        Examples:
            Paths under home shorten to the `~` form::

                >>> from my.apis import fs
                >>> fs.shortpath(fs.home / 'notes' / 'todo.md')
                '~/notes/todo.md'
        """
        if not path:
            return ''
        path = cls.path(path)

        ancestors = {'.': Path.cwd(), '~': Path.home(), **cls.PATH_VARS}
        return next(
            (str(Path(k, r)) for k, v in ancestors.items() if (r := cls.relativize(path, v))),
            '',
        )


#: Define a default--and thus "naive local", so-to-speak--instance of the type.
FS = Filesystem()

#: An alias for "FS""
fs = FS

#: An alias for "FS"
PATHS = FS
