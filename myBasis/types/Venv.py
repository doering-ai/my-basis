"""Virtual Environment finder.

COPYRIGHT NOTE: This file is--unlike almost any other file in this repo so far--adapted directly
from an existing plugin: `LSP-pyright`'s `venv_finder.py`, which is governed under the
`MIT` license:

> Copyright (c) 2019 SublimeLSP
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any, NamedTuple, Callable, ClassVar
from typing_extensions import Self

from configparser import ConfigParser
from pathlib import Path
from enum import Flag, auto
import asyncio as aio
import contextlib as ctx
import functools as ft
import itertools as it
import json
import os

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ..infra.utils import ut


############
### DATA ###
############
RGXS = ut.rgx_dict(
    finder_detritus=r'(?i)^_+(?:find)?|_+(?:(?:venv_?)?find(?:er)?)?$',
    version=r'(\d+)(?:\.(\d+))?(?:\.(\d+))?',
    venv_map_item=r'(?mi)^\s*venv\s*[:=]\s*(\S.*)$',
)
IS_WINDOWS = os.name == 'nt'


class Kind(Flag):
    NONE = 0
    POETRY = auto()
    HATCH = auto()
    PDM = auto()
    RYE = auto()
    UV = auto()
    PYENV = auto()
    PIPENV = auto()
    VENV = auto()
    CONDA = auto()
    SUBLIME = auto()


class Framework(NamedTuple):
    cmd: str = ''
    args: str = ''
    file: str = ''
    parent_index: int = 0
    parser: Callable[[str], str] | None = None

    @staticmethod
    def _seek_map_item(output: str) -> str:
        return m[1] if (m := RGXS['venv_map_item'].search(output)) else ''

    @property
    def kind(self) -> Kind:
        return Kind.__members__.get(self.cmd.strip().upper(), Kind.NONE)


FRAMEWORKS = [
    Framework('hatch', 'env find', ''),
    Framework('pdm', 'info --python', '.pdm-python', 2),
    Framework('pipenv', '--py', 'Pipfile', 2),
    Framework('poetry', 'env info -p', 'poetry.lock'),
    Framework('pyenv', 'which python', '', 2),
    Framework('rye', 'show', 'pyproject.toml', 2, Framework._seek_map_item),
]


############
### BODY ###
############
class Venv(pyd.BaseModel):
    """A discovered or proposed Python virtual environment.

    Fields are populated either directly on construction or lazily via `concretize()`, which
    iterates the registered finder chain until one resolves a valid root directory.

    A `Venv` instance is truthy only once both `root` is a valid directory **and** `kind` has been
    determined (i.e. after a successful `concretize()` or explicit construction with both fields).
    """

    Kind: ClassVar[type[Kind]] = Kind

    # ---- Independent (arguments) ----
    #: The raw path of the initial path passed to the guess function
    raw: str = ''
    #: The window for which this virtual environment was loaded.
    window: ut.WindowField | None = None
    #: The resolved version of the initial path.
    origin: pyd.DirectoryPath = Path('/')

    # ---- Dependent (states) ----
    #: The "home" of the environment (i.e. where `pyproject.toml` is)
    home: pyd.DirectoryPath = Path('/')
    #: The root of the actual virtual environment. (i.e. where `lib/`  and `bin/` are.)
    root: pyd.DirectoryPath = Path('/')
    #: The type of venv that this represents.
    kind: Kind = Kind.NONE

    #: The prompt of the virtual environment.
    prompt: str = ''
    #: The Python version of the virtual environment.
    python_version: str = ''
    #: Any available config information from `pyenv.cfg` or `conda info`.
    data: dict[str, Any] = {}

    _recursed: bool = pyd.PrivateAttr(default=False)

    # -------------------
    # `.` Initial Methods
    # -------------------

    # -------------------
    # `-` Private Methods
    # -------------------
    @ft.cached_property
    def clean_version(self) -> tuple[str, str, str]:
        """Parse `python_version` into a ``(major, minor, patch)`` string triple.

        Each element is a digit string or ``''`` if that component was absent.
        Raises `ValueError` if `python_version` contains no recognisable version number.
        """
        match = RGXS['version'].search(self.python_version)
        if not match:
            raise ValueError(f'Invalid Python version: {self.python_version}')
        return match[1] or '3', match[2] or '', match[3] or ''

    # -------------------
    # `+` Primary Methods
    # -------------------
    async def get_conda_info(self) -> dict | None:
        """Return the output of ``conda info --json`` as a dict, or `None` if not a conda env.

        Detection is based on the presence of a ``conda-meta/`` directory inside `self.path`.
        """
        if (self.origin / 'conda-meta').is_dir():
            if _ret := await ut.exa('conda', 'info', '--json', cwd=self.origin):
                with ctx.suppress(json.JSONDecodeError):
                    return json.loads(_ret)
        return None

    async def get_pyvenv_info(self) -> dict | None:
        """Return the key-value pairs from ``<root>/pyvenv.cfg`` as a dict, or `None` if absent.

        The file is parsed with `configparser` after injecting a synthetic ``[USER]`` section
        header, which is the standard technique for INI-like files that lack section names.
        """
        if (pyenv := self.root / 'pyvenv.cfg').is_file():
            config = ConfigParser()
            config.read_string(f'[USER]\n{pyenv.read_text()}')
            return dict(config.items('USER'))
        return None

    async def check_env(self) -> Path | None:
        """Check for virtual environment indicators in the envvars and project settings.

        See https://www.sublimetext.com/docs/projects.html and
            https://packages.sublimetext.io/packages/Virtualenv
        """
        # I. Check VARIABLES
        if root := os.getenv('CONDA_PREFIX'):
            self.kind = Kind.CONDA
        elif root := os.getenv('VIRTUAL_ENV'):
            self.kind = Kind.VENV

        # II. Check SETTINGS
        elif (
            self.window
            and (project := self.window.project_data())
            and isinstance(project, dict)
            and (root := project.get('virtualenv', ''))
        ):
            self.kind = Kind.SUBLIME
        else:
            return None

        root = ut.normalize_path(root, self.window)
        if ut.is_valid_path(root):
            return root
        else:
            print(f'[WARN] {self.kind} produced invalid root `{root}`')
            return None

    async def check_path(self) -> Path | None:
        """Check the given path for virtual environments rooted in it or one of its ancestors."""
        # I. List out all our ancestors, assuming no mad person out there dares to use a root below
        #    their home directory.
        assert self.origin and self.origin.is_dir(), f'Origin path {self.origin} is not valid.'
        _home = Path.home()
        candidates = list(it.takewhile(lambda p: p != _home, (self.origin, *self.origin.parents)))
        if not candidates:
            print(f'[DEBUG] No valid candidate paths found for {self.origin}.')
            return None

        # II. Walk up the tree until one returns a path to its venv
        for candidate in candidates:
            if root := await self._check_candidate(candidate):
                self.home = candidate
                self.root = root
                return root
        return None

    async def _check_candidate(self, path: pyd.DirectoryPath) -> pyd.DirectoryPath | None:
        # I. Any pyvenv-centered frameworks (incl. `uv`) docs.python.org/library/venv.html
        names = ('.venv', 'venv')
        if child := next((p for n in names if (p := path / n).is_dir()), None):
            ret = child
            self.kind = Kind.VENV
            return ret

        # II. All other frameworks
        for fw in FRAMEWORKS:
            # II.i. Check for `file`
            if fw.file and not (path / fw.file).exists():
                continue

            # II.ii. Run command
            _ret = await ut.exa(fw.cmd, fw.args, cwd=path)

            # II.iii. Apply parser & normalize
            if fw.parser:
                _ret = fw.parser(_ret or '')
            _ret = (_ret or '').strip()
            if not _ret:
                continue

            ret = ut.normalize_path(_ret, self.window)
            if not ut.is_valid_path(ret):
                print(f'[WARN] Command `{fw.cmd} {fw.args}` returned invalid path `{_ret}`')
                continue

            # II.iii. Adjust for parents
            if fw.parent_index:
                for _ in range(fw.parent_index):
                    if not ret.parent:
                        print(
                            f'[WARN] Command `{fw.cmd} {fw.args}` returned path `{_ret}` which is '
                            f'not deep enough for parent index {fw.parent_index}'
                        )
                        return None
                    ret = ret.parent

            self.kind = fw.kind
            return ret
        return None

    # ------------------
    # `*` Public Methods
    # ------------------
    def __bool__(self) -> bool:
        """Whether this virtual environment is valid."""
        return bool(ut.is_valid_path(self.root) and self.kind is not Kind.NONE)

    @ft.cached_property
    def bin(self) -> Path:
        """The path of the `bin` directory of the virtual environment."""
        return self.root / ('Scripts' if IS_WINDOWS else 'bin')

    @ft.cached_property
    def lib(self) -> Path:
        """The path of the `lib` directory of the virtual environment."""
        return self.root / ('Lib' if IS_WINDOWS else 'lib')

    @ft.cached_property
    def site_packages(self) -> Path:
        """The path of the `site-packages` directory of the virtual environment."""
        ret = self.lib / 'site-packages'
        if not IS_WINDOWS:
            _parts = list(ret.parts)
            _parts.insert(len(_parts) - 1, f'python{".".join(self.clean_version[:2])}')
            ret = Path(*_parts)
        return ret

    @ft.cached_property
    def python_executable(self) -> Path:
        """The path of the Python executable of the virtual environment."""
        ret = self.bin / 'python'
        if IS_WINDOWS:
            ret = ret.with_suffix('.exe')
        assert ret.exists() and ret.is_file(), f'Python executable not found at {ret}'
        return ret

    @property
    def exact_match(self) -> bool:
        """Whether the virtual environment was resolved from an exact match with the origin path."""
        return self.home == self.origin

    #######################
    ### FINDER REGISTRY ###
    #######################
    async def find(self, origin: Path) -> Self:
        """Resolve the virtual environment by running each registered finder in order.

        Short-circuits immediately if the instance is already valid (i.e. `bool(self)` is True).
        On the first finder that returns a usable path, `setup_root()` is called to populate the
        remaining fields

        Returns:
            `True` if a match was found, `False` otherwise.
        """
        if self:
            return self
        self.raw = str(origin)
        origin = ut.normalize_path(origin, self.window)
        if origin.is_file():
            origin = origin.parent
        self.origin = origin

        # I. First check the shell environment, then for individual subfiles & PATH commands
        if root := await self.check_env():
            self.root = root
        elif root := await self.check_path():
            self.root = root
        else:
            print(f'No virtual environment found for {self.origin}.')
            return self

        # I. Query tools for the binary's path and version, if we can
        if info := await self.get_pyvenv_info():
            # I. General/PEP-backed case, where `pyvenv.cfg` is the origin of truth
            self.prompt = info.get('prompt', self.root.name)
            # `venv` uses "version", and `uv` uses "version_info"
            self.python_version = info.get('version', info.get('version_info', ''))
        elif info := await self.get_conda_info():
            # II. Conda-specific case, where we can read the venv's properties from the CLI
            self.prompt = info.get('active_prefix_name', '')
            self.python_version = (
                info.get('python_version', '')
                .replace('.alpha.', 'a')
                .replace('.beta.', 'b')
                .replace('.candidate.', 'rc')
                .partition('.final.')[0]
            )
        return self

    @ft.wraps(find)
    def sync_find(self, origin: Path) -> Self:  # noqa: D102
        return aio.run(self.find(origin))


__all__ = ['Venv']
