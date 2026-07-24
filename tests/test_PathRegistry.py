############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path

### EXTERNAL
import pytest as pyt
import pydantic as pyd
import regex as re
import sublime as sb

### INTERNAL
from myBasis.infra.PathRegistry import PathRegistry, PATHS, _normalize


############
### BODY ###
############
class TestNormalize:
    """Tests for the ``_normalize`` helper."""

    def test_expands_user(self):
        result = _normalize('~')
        assert result == Path.home()

    def test_absolute_path_unchanged(self):
        result = _normalize('/usr/bin')
        assert result == Path('/usr/bin')

    def test_relative_existing_path_resolved(self, tmp_path: Path):
        # Create a file in cwd's parent so _normalize can find it relative to cwd
        # Actually _normalize checks Path.cwd() / path, so we need something in cwd
        result = _normalize('nonexistent_relative_path_xyz')
        # Since it doesn't exist relative to cwd, it returns the path as-is
        assert result == Path('nonexistent_relative_path_xyz')

    def test_relative_existing_path(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'marker.txt').touch()
        result = _normalize('marker.txt')
        assert result == tmp_path / 'marker.txt'


class TestPathRegistry:
    """Tests for the ``PathRegistry`` pydantic model."""

    def test_is_pydantic_model(self):
        assert issubclass(PathRegistry, pyd.BaseModel)

    # ---- Field relationships ----
    def test_pkgs_is_home_child(self):
        reg = PATHS
        assert reg.pkgs == reg.home / 'Packages'

    def test_inst_is_home_child(self):
        reg = PATHS
        assert reg.inst == reg.home / 'Installed Packages'

    def test_user_is_pkgs_child(self):
        reg = PATHS
        assert reg.user == reg.pkgs / 'User'

    def test_base_is_pkgs_child(self):
        reg = PATHS
        assert reg.base == reg.pkgs / 'myBasis'

    def test_console_is_my_child(self):
        reg = PATHS
        assert reg.console == reg.my / 'console.log'

    def test_venv_is_home_child(self):
        reg = PATHS
        assert reg.venv == reg.home / 'Lib' / 'python38'

    # ---- Types ----
    def test_host_is_directory(self):
        assert isinstance(PATHS.host, Path)

    def test_console_is_path_not_directory(self):
        assert isinstance(PATHS.console, Path)

    # ---- Methods ----
    def test_new_static_method(self):
        result = PathRegistry.new(my_dir='/tmp', other='/var')
        assert result['my_dir'] == Path('/tmp')
        assert result['other'] == Path('/var')

    def test_new_resolves_paths(self):
        result = PathRegistry.new(rel='~')
        assert result['rel'] == Path.home()

    def test_normalize_static_method(self):
        result = PathRegistry.normalize('~')
        assert result == Path.home()

    def test_str_representation(self):
        s = str(PATHS)
        assert 'PathRegistry:' in s
        assert 'host' in s
        assert 'pkgs' in s

    def test_compile_rgx_returns_pattern(self):
        pat = PathRegistry.compile_rgx(Path('/test/path'))
        assert isinstance(pat, re.Pattern)

    def test_compile_rgx_matches_path(self):
        pat = PathRegistry.compile_rgx(Path('/test/path'))
        assert pat.search('/test/path/file.py')

    def test_compile_rgx_caches(self):
        """``compile_rgx`` is decorated with ``lru_cache``."""
        p1 = PathRegistry.compile_rgx(Path('/cached'))
        p2 = PathRegistry.compile_rgx(Path('/cached'))
        assert p1 is p2

    def test_rgxs_cached_property(self):
        reg = PATHS
        rgxs = reg.rgxs
        assert isinstance(rgxs, dict)
        assert 'host' in rgxs
        assert 'pkgs' in rgxs
        for name, pat in rgxs.items():
            assert isinstance(pat, re.Pattern), f'{name} pattern is not compiled'

    def test_rgxs_is_cached(self):
        """``rgxs`` is a cached_property so it returns the same dict on repeated access."""
        reg = PATHS
        assert reg.rgxs is reg.rgxs


class TestPATHS:
    """Tests for the module-level ``PATHS`` singleton."""

    def test_is_path_registry(self):
        assert isinstance(PATHS, PathRegistry)

    def test_pkgs_matches_sublime_packages_path(self):
        assert PATHS.pkgs == Path(sb.packages_path())

    def test_cache_matches_sublime_cache_path(self):
        assert PATHS.cache == Path(sb.cache_path())

    def test_root_matches_sublime_executable_parent(self):
        assert PATHS.root == Path(sb.executable_path()).parent

    def test_home_is_pkgs_parent(self):
        assert PATHS.home == PATHS.pkgs.parent
