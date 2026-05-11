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
from ..infra import INFRA_PATHS
from ..utils import ut
from ..regex import RegexStore
from ..typing import typist
from ..types import Platform
from .Environment import env


class Convention(pyd.BaseModel):
    """A model representing a single user directory convention.

    A dictionary mapping platforms to their user directory conventions.
    The inner dictionary maps a key (like `config`, `cache`, or `data`) to a tuple of an
    environment variable and a default path.
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
        """Load platform conventions from the YAML file and populate the `CONVENTIONS` map."""
        text = (INFRA_PATHS.data / 'platform-conventions.yaml').read_text()
        data = typist.from_yaml(text, dict[str, dict[str, tuple[str, str]]])

        return {
            Platform[_platform.upper()]: Convention(**_plat_data)
            for _platform, _plat_data in data.items()
        }

    def resolve(self, envvar: str, default: str) -> Path:
        """Resolve the given field in this environment, returning the default if necessary."""
        return ut.path(os.getenv(envvar, default))


############
### DATA ###
############
#: Regexes, mostly for for identifying directories.
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

#: A sentinel value that communicates a failure of some kind, or an unininitialized register.
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
    """A registry of file paths, mapping string names to Path objects."""

    RGXS: ClassVar[RegexStore] = RGXS

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
        if match := RGXS['leaf'].search('\n'.join(map(Path.as_posix, leaves))):
            return match[1]
        elif match := RGXS['branch'].search('\n'.join(map(Path.as_posix, branches))):
            return match[1]
        return None

    # -------------------
    # `+` Primary Methods
    # -------------------
    @staticmethod
    @ft.lru_cache(maxsize=256)
    def compile_rgx(path: Path | str) -> re.Pattern[str]:
        """Compile a regex pattern matching the given path, allowing for relative leading parts."""
        pathstr = re.escape(Path(path).as_posix().strip('/'))
        expr = ut.multi_rgx(
            r'(?<![-\w\/.])',
            r'(?:\.{0,2}\/)+',
            rf'({pathstr})',
            r'(?![-.\w])(\/?)',
        )
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
        """A list of regex patterns matching the paths in this registry."""
        return {name: self.compile_rgx(path) for name, path in reversed(self.model_dump().items())}

    @classmethod
    def is_possible(cls, raw: str | Path | None) -> bool:
        """Check if the given path isn't empty."""
        return bool(raw and (_p := cls.path(raw)).root and str(_p).strip('./\\ '))

    @classmethod
    def is_actual(cls, raw: str | Path | None) -> bool:
        """Check if the given path actually exists."""
        return bool(raw and cls.is_possible(path := cls.path(raw)) and path.exists())

    @classmethod
    def path(cls, raw: str | Path | None) -> Path:
        """Normalizes a path -- see `ut.path()` for documentation."""
        return ut.path(raw)

    @classmethod
    def is_relative_to(cls, child: Path | str, parent: Path | str) -> bool:
        """Naively check if the child is relative to the proposed parent.

        Args:
            child: Path to check.
            parent: Proposed parent path.
        Returns:
            Whether the child is relative to parent.
        """
        return str(child).startswith(str(parent))

    @classmethod
    def relativize(cls, path: Path, *parents: Path | str) -> Path | None:
        """Relativize the given path to the first matching parent, if possible.

        Args:
            path: Path to relativize.
            *parents: One or more parent paths to check against.
        Returns:
            The same path but relevant to one of the parents if possible, otherwise None.
        """
        return next(
            (
                path.relative_to(parent)
                for parent in map(cls.path, parents)
                if cls.is_relative_to(path, parent)
            ),
            None,
        )

    @classmethod
    def seek_project(cls, path: Path | None = None) -> Path | None:
        """Attempt to find the project root by looking for common indicators.

        Args:
            path: Starting path to search from. If a file is given, the parent will be used.
            depth: Maximum number of ancestor levels to check. Use -1 for unlimited.
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


#: Define a default--and thus "naive local", so-to-speak--instance of the type.
FS = Filesystem()

#: An alias for "FS""
fs = FS

#: An alias for "FS"
PATHS = FS
