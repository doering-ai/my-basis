############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any
from collections.abc import MutableSequence
from pathlib import Path
import importlib
import time

### EXTERNAL
import pytest as pyt
import regex as re

### INTERNAL
from my.apis.Filesystem import Filesystem, Convention, NOWHERE, RGXS
from my.types import Platform
from ..conftest import boolmap, Patch

cls = Filesystem


############
### BODY ###
############
class TestConvention:
    """Test suite for Convention."""

    def test_conventions__returns_platform_dict(self):
        """Test conventions() returns a dict keyed by Platform members."""
        result = Convention.conventions()
        assert isinstance(result, dict)
        assert all(isinstance(k, Platform) for k in result)
        assert all(isinstance(v, Convention) for v in result.values())

    def test_conventions__cached(self):
        """Test conventions() returns the same object on repeated calls."""
        assert Convention.conventions() is Convention.conventions()

    def test_conventions__has_local_platform(self):
        """Test conventions() includes an entry for the current platform."""
        assert Platform.local() in Convention.conventions()

    def test_resolve__returns_path(self, patch: Patch):
        """Test resolve always returns a Path instance."""
        patch.delenv('_MYTEST_XYZ', raising=False)
        result = Convention().resolve('_MYTEST_XYZ', '~/.config')
        assert isinstance(result, Path)

    def test_resolve__uses_default(self, patch: Patch):
        """Test resolve falls back to the default path when the env var is unset."""
        patch.delenv('_MYTEST_XYZ', raising=False)
        result = Convention().resolve('_MYTEST_XYZ', '/fallback/path')
        assert isinstance(result, Path)

    def test_resolve__uses_envvar(self, patch: Patch, tmp_path: Path):
        """Test resolve returns the env var value when it is set."""
        patch.setenv('_MYTEST_XYZ', str(tmp_path))
        result = Convention().resolve('_MYTEST_XYZ', '/fallback')
        assert result == tmp_path


class TestFilesystem:
    """Test suite for Filesystem."""

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.fixture
    def fs(self) -> Filesystem:
        """Fresh Filesystem instance."""
        return cls()

    def test_init__basic(self, fs: Filesystem):
        """Test Filesystem instantiates without error."""
        assert isinstance(fs, cls)

    def test_init__home_is_dir(self, fs: Filesystem):
        """Test home field resolves to an existing directory."""
        assert fs.home.is_dir()

    def test_init__fields_are_paths(self, fs: Filesystem):
        """Test all non-platform fields are Path instances."""
        for field, value in fs.model_dump().items():
            if field == 'plat':
                continue
            assert isinstance(value, Path), f'{field!r} should be a Path'

    def _setup_paths(
        self, root: Path, *paths: str | tuple[str, str] | Path | tuple[Path, str]
    ) -> None:
        pairs = []
        for raw in paths:
            if isinstance(raw, tuple):
                assert len(raw) == 2, f'Invalid path tuple: {raw!r}'
                raw, text = raw
            else:
                text = ''
            path, raw = root / raw, str(raw)
            pairs.append((path, raw))

        for path, raw in pairs:
            if raw.endswith('/'):
                path.mkdir()
                continue
            if not text:
                if path.suffix in ('.json', '.jsn'):
                    text = '{}'
                elif path.suffix in ('.toml', '.tml'):
                    text = '[tool]'
                else:
                    text = 'test'
            path.write_text(text)

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'paths, expected',
        boolmap(
            true=[
                [('pyproject.toml', '[project]')],
                ['Taskfile'],
                ['Makefile'],
                ['uv.lock'],
                [('.gitignore', '*.pyc')],
                ['.git/'],
                ['.venv/'],
            ],
            false=[
                ['data/', 'test/', 'notes.text'],
            ],
        ),
    )
    def test_check_for_project_root(
        self, paths: MutableSequence[str | tuple[str, str]], expected: bool, tmp_path: Path
    ):
        """Test pyproject.toml is recognized as a leaf project indicator."""
        self._setup_paths(tmp_path, *paths)
        assert bool(cls._check_for_project_root(tmp_path)) == expected

    def test_check_for_project_root__enforces_timeout_on_raw_pattern(
        self, tmp_path: Path, patch: Patch
    ):
        """Test that the raw `RGXS['leaf']` accessor still respects a timeout.

        Regression test: `RGXS['leaf']`/`RGXS['branch']` hand back the bare compiled pattern
        (subscripting a `RegexStore` bypasses its own timeout-guarded `search()`), so
        `_check_for_project_root` must pass `timeout=` explicitly at its call sites. Before that
        fix, swapping in a pathological (catastrophic-backtracking) pattern here would hang
        indefinitely -- confirmed separately to still be running past 8 seconds on this exact
        input with no `timeout=` at all. With the fix, it raises `TimeoutError` almost instantly.
        """
        # `import my.apis.Filesystem as x` (and pytest's dotted-string `setattr` form, which
        # resolves the same way) would both bind to the `Filesystem` *class* here, not the
        # module -- `my/apis/__init__.py` re-exports the class under the submodule's own name,
        # shadowing it on the `my.apis` package. `importlib.import_module` bypasses that.
        fs_module = importlib.import_module('my.apis.Filesystem')
        patch.setattr(fs_module, 'REGEX_TIMEOUT', 0.2)
        patch.setitem(RGXS.patterns, 'leaf', re.compile(r'(a|a)+b'))
        (tmp_path / ('a' * 30 + 'c')).write_text('x')

        start = time.monotonic()
        with pyt.raises(TimeoutError):
            cls._check_for_project_root(tmp_path)
        assert time.monotonic() - start < 5, 'timeout should fire well before this bound'

    # ------------------
    # `*` Public Methods
    # ------------------
    # ------------
    # `*2` Methods
    # ------------
    @pyt.mark.parametrize(
        'raw, expected',
        boolmap(
            true=[str(Path.home()), '/usr'],
            false=['', None],
        ),
    )
    def test_is_possible(self, raw: str | None, expected: bool):
        """Test is_possible returns True only for resolved, non-empty absolute paths."""
        assert cls.is_possible(raw) == expected

    @pyt.mark.parametrize(
        'raw, expected',
        boolmap(
            true=[str(Path.home())],
            false=['', None, '/nonexistent_path_xyz_12345'],
        ),
    )
    def test_is_actual(self, raw: str | None, expected: bool):
        """Test is_actual returns True only for paths that exist on disk."""
        assert cls.is_actual(raw) == expected

    def test_is_actual__tmp_dir(self, tmp_path: Path):
        """Test is_actual returns True for a real temporary directory."""
        assert cls.is_actual(tmp_path)

    @pyt.mark.parametrize(
        'raw, expected',
        [
            (None, NOWHERE),
            ('', NOWHERE),
            ('/some/absolute/path', Path('/some/absolute/path')),
            ('~/path', Path('~/path').expanduser()),
            ('$HOME/path', Path('~/path').expanduser()),
        ],
        ids=['None', 'Empty String', 'Absolute Path', 'Tilde Expansion', 'Env Var Expansion'],
    )
    def test_path(self, raw: Any, expected: Path):
        """Test path() always returns a Path instance."""
        print(f'[test_path] raw: {raw}, new_path: {cls.path(raw)}')
        path = cls.path(raw)
        assert path == expected

    @pyt.mark.parametrize(
        'child, parent, expected',
        boolmap(
            true=[
                ('/home/user/project/src', '/home/user/project'),
                ('/home/user/project', '/home/user'),
                ('/home/user', '/home/user'),
            ],
            false=[
                ('/home/user/project', '/home/other'),
                ('/tmp/project', '/home/user'),
                ('/home/user', '/home/user/project'),
                ('/srv/app2', '/srv/app'),  # Sibling sharing a string prefix (regression)
            ],
        ),
    )
    def test_is_relative_to(self, child: str, parent: str, expected: bool):
        """Test is_relative_to detects child/parent relationships segment-aware."""
        assert cls.is_relative_to(child, parent) == expected

    def test_relativize__basic(self):
        """Test relativize returns the child relative to a matching parent."""
        parent = Path.home()
        child = parent / 'documents' / 'file.txt'
        assert cls.relativize(child, parent) == Path('documents/file.txt')

    def test_relativize__first_parent_wins(self):
        """Test relativize uses the first matching parent in priority order."""
        parent_long = Path.home() / 'documents'
        parent_short = Path.home()
        child = parent_long / 'file.txt'
        assert cls.relativize(child, parent_long, parent_short) == Path('file.txt')

    def test_relativize__second_parent_fallback(self):
        """Test relativize falls back to the second parent when the first does not match."""
        real = Path.home()
        child = real / 'test'
        assert cls.relativize(child, Path('/nonexistent_xyz'), real) == Path('test')

    def test_relativize__no_match(self):
        """Test relativize returns None when no parent matches."""
        child = Path.home() / 'test'
        assert cls.relativize(child, Path('/nonexistent_a'), Path('/nonexistent_b')) is None

    def test_seek_project__from_file(self, tmp_path: Path):
        """Test seek_project finds the ancestor with pyproject.toml when given a file."""
        project = tmp_path / 'project'
        project.mkdir()
        (project / 'pyproject.toml').write_text('[project]')
        src = project / 'src'
        src.mkdir()
        file = src / 'main.py'
        file.write_text('')
        assert cls.seek_project(file) == project

    def test_seek_project__from_subdir(self, tmp_path: Path):
        """Test seek_project finds the ancestor with Taskfile when given a subdirectory."""
        project = tmp_path / 'project'
        project.mkdir()
        (project / 'Taskfile').write_text('')
        sub = project / 'src' / 'module'
        sub.mkdir(parents=True)
        assert cls.seek_project(sub) == project

    def test_seek_project__no_indicators(self, tmp_path: Path):
        """Test seek_project returns None when no ancestor contains project indicators."""
        sub = tmp_path / 'a' / 'b' / 'c'
        sub.mkdir(parents=True)
        assert cls.seek_project(sub) is None

    def test_seek_project__stops_at_home(self, tmp_path: Path, patch: Patch):
        """Test seek_project returns None immediately when an ancestor equals home."""
        sub = tmp_path / 'sub'
        sub.mkdir()
        # Make home() return tmp_path so the first ancestor in sub.parents triggers the stop
        patch.setattr(Path, 'home', staticmethod(lambda: tmp_path))
        assert cls.seek_project(sub) is None
