############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Any

### EXTERNAL
import pytest as pyt

### INTERNAL
from myBasis.types.Venv import Venv, _FINDERS


############
### DATA ###
############
def _run(coro: Any) -> Any:
    """Run a coroutine synchronously for use in non-async test methods."""
    return asyncio.run(coro)


def _make_venv(tmp_path: Path, python_version: str = '3.8.12') -> Venv:
    """Construct a fully valid Venv pointing at *tmp_path*."""
    venv = Venv.model_construct(
        raw=str(tmp_path),
        path=tmp_path,
        root=tmp_path,
        kind='venv',
        finder='directory',
        prompt=tmp_path.name,
        python_version=python_version,
        data={},
        window=None,
    )
    # PrivateAttr must be set separately after model_construct
    object.__setattr__(venv, '_recursed', False)
    return venv


############
### BODY ###
############
class TestVenvBool:
    """Tests for `Venv.__bool__`."""

    def test_false_when_default(self):
        """An empty Venv (no root, no kind) is falsy."""
        venv = Venv.model_construct(root=Path('/'), kind='', python_version='')
        object.__setattr__(venv, '_recursed', False)
        assert not venv

    def test_false_when_missing_kind(self, tmp_path: Path):
        """A Venv with a valid root but no kind is falsy."""
        venv = Venv.model_construct(root=tmp_path, kind='')
        object.__setattr__(venv, '_recursed', False)
        assert not venv

    def test_false_when_root_nonexistent(self, tmp_path: Path):
        """A Venv whose root directory does not exist is falsy."""
        venv = Venv.model_construct(root=tmp_path / 'nonexistent', kind='venv')
        object.__setattr__(venv, '_recursed', False)
        assert not venv

    def test_true_when_valid(self, tmp_path: Path):
        """A Venv with an existing root and a non-empty kind is truthy."""
        venv = _make_venv(tmp_path)
        assert venv


class TestVenvCleanVersion:
    """Tests for `Venv.clean_version`."""

    @pyt.mark.parametrize(
        'version, expected',
        [
            ('3.8.12', ('3', '8', '12')),
            ('3.8', ('3', '8', '')),
            ('3', ('3', '', '')),
            ('10.20.300', ('10', '20', '300')),
            # Version embedded in a longer string (e.g. from pyvenv.cfg)
            ('Python 3.9.7', ('3', '9', '7')),
            ('version = 3.8.12', ('3', '8', '12')),
        ],
    )
    def test_parses(self, tmp_path: Path, version: str, expected: tuple[str, str, str]):
        venv = _make_venv(tmp_path, python_version=version)
        assert venv.clean_version == expected

    def test_raises_on_invalid(self, tmp_path: Path):
        venv = _make_venv(tmp_path, python_version='no-version-here')
        with pyt.raises(ValueError, match='Invalid Python version'):
            _ = venv.clean_version


class TestVenvPaths:
    """Tests for the cached path properties: `bin`, `lib`, `python_executable`, `site_packages`."""

    def test_bin(self, tmp_path: Path):
        venv = _make_venv(tmp_path)
        assert venv.bin == tmp_path / 'bin'

    def test_lib(self, tmp_path: Path):
        venv = _make_venv(tmp_path)
        assert venv.lib == tmp_path / 'lib'

    def test_python_executable(self, tmp_path: Path):
        venv = _make_venv(tmp_path)
        assert venv.python_executable == tmp_path / 'bin' / 'python'

    @pyt.mark.parametrize(
        'python_version, expected_rel',
        [
            ('3.8.12', 'lib/python3.8/site-packages'),
            ('3.10.0', 'lib/python3.10/site-packages'),
            ('3.11', 'lib/python3.11/site-packages'),
        ],
    )
    def test_site_packages(self, tmp_path: Path, python_version: str, expected_rel: str):
        venv = _make_venv(tmp_path, python_version=python_version)
        assert venv.site_packages == tmp_path / expected_rel

    def test_validate_raises_for_invalid_root(self, tmp_path: Path):
        """Path properties raise ValueError when the root does not exist."""
        venv = _make_venv(tmp_path / 'missing')
        # `_validate` is called inside `bin`
        with pyt.raises(ValueError):
            _ = venv.bin


class TestGetPyvenvInfo:
    """Tests for `Venv.get_pyvenv_info()`."""

    def test_returns_none_when_no_file(self, tmp_path: Path):
        venv = _make_venv(tmp_path)
        result = _run(venv.get_pyvenv_info())
        assert result is None

    @pyt.mark.parametrize(
        'cfg_content, key, expected',
        [
            ('home = /usr/bin\npython = 3.8.12', 'python', '3.8.12'),
            ('home = /usr/bin\nversion = 3.9.0\nprompt = myenv', 'prompt', 'myenv'),
            ('version_info = 3.10.1\nhome = /usr/bin', 'version_info', '3.10.1'),
        ],
    )
    def test_parses_cfg(self, tmp_path: Path, cfg_content: str, key: str, expected: str):
        (tmp_path / 'pyvenv.cfg').write_text(cfg_content)
        venv = _make_venv(tmp_path)
        result = _run(venv.get_pyvenv_info())
        assert result is not None
        assert result[key] == expected

    def test_returns_all_keys(self, tmp_path: Path):
        """All key-value pairs from pyvenv.cfg are present in the returned dict."""
        (tmp_path / 'pyvenv.cfg').write_text('home = /usr/bin\nversion = 3.8.12\nprompt = test')
        venv = _make_venv(tmp_path)
        result = _run(venv.get_pyvenv_info())
        assert result is not None
        assert set(result.keys()) >= {'home', 'version', 'prompt'}


class TestGetCondaInfo:
    """Tests for `Venv.get_conda_info()`."""

    def test_returns_none_when_no_conda_meta(self, tmp_path: Path):
        """No conda-meta directory → None, regardless of conda installation."""
        venv = _make_venv(tmp_path)
        result = _run(venv.get_conda_info())
        assert result is None

    def test_returns_none_when_conda_fails(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        """conda-meta present but `conda info --json` fails → None."""
        (tmp_path / 'conda-meta').mkdir()
        import myBasis.infra.utils as utils_module

        monkeypatch.setattr(utils_module.Utils, 'exa', staticmethod(lambda *a, **kw: _async(None)))
        venv = _make_venv(tmp_path)
        venv.path = tmp_path
        result = _run(venv.get_conda_info())
        assert result is None


class TestFinders:
    """Tests for the registered finder methods."""

    # ---- find__envvar ----
    def test_envvar_returns_path(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setenv('VIRTUAL_ENV', str(tmp_path))
        venv = _make_venv(tmp_path)
        result = _run(_FINDERS['envvar'](venv))
        assert result is not None
        assert Path(result).resolve() == tmp_path.resolve()

    def test_envvar_returns_none_when_unset(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.delenv('VIRTUAL_ENV', raising=False)
        venv = _make_venv(tmp_path)
        result = _run(_FINDERS['envvar'](venv))
        assert result is None

    # ---- find__conda_envvar ----
    def test_conda_envvar_returns_path(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setenv('CONDA_PREFIX', str(tmp_path))
        venv = _make_venv(tmp_path)
        result = _run(_FINDERS['conda_envvar'](venv))
        assert result is not None

    def test_conda_envvar_returns_none_when_unset(
        self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch
    ):
        monkeypatch.delenv('CONDA_PREFIX', raising=False)
        venv = _make_venv(tmp_path)
        result = _run(_FINDERS['conda_envvar'](venv))
        assert result is None

    # ---- find__directory ----
    @pyt.mark.parametrize('name', ['.venv', 'venv'])
    def test_directory_finds_named_venv(self, tmp_path: Path, name: str):
        (tmp_path / name).mkdir()
        venv = _make_venv(tmp_path)
        venv.path = tmp_path
        result = _run(_FINDERS['directory'](venv))
        assert result == tmp_path / name

    def test_directory_returns_none_when_absent(self, tmp_path: Path):
        venv = _make_venv(tmp_path)
        venv.path = tmp_path
        result = _run(_FINDERS['directory'](venv))
        assert result is None

    # ---- find__recursive ----
    def test_recursive_skips_hidden_dirs(self, tmp_path: Path):
        (tmp_path / '.hidden').mkdir()
        (tmp_path / '_internal').mkdir()
        venv = _make_venv(tmp_path)
        venv.path = tmp_path
        # Neither child triggers concretize, so None is returned
        result = _run(_FINDERS['recursive'](venv))
        assert result is None

    def test_recursive_respects_guard(self, tmp_path: Path):
        """Re-entrant calls (when `_recursed` is True) return None immediately."""
        venv = _make_venv(tmp_path)
        venv.path = tmp_path
        object.__setattr__(venv, '_recursed', True)
        result = _run(_FINDERS['recursive'](venv))
        assert result is None


class TestConcretize:
    """Tests for `Venv.concretize()`."""

    def test_short_circuits_when_already_valid(self, tmp_path: Path):
        """A truthy venv returns True immediately without calling any finder."""
        venv = _make_venv(tmp_path)
        assert bool(venv)
        result = _run(venv.concretize())
        assert result is True

    def test_returns_false_when_no_finder_matches(
        self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch
    ):
        """Returns False and leaves the venv invalid when all finders return None."""
        import myBasis.types.Venv as venv_module  # noqa

        async def _null_finder(self: Venv) -> None:
            return None

        monkeypatch.setattr(venv_module, '_FINDERS', {'null': _null_finder})
        venv = Venv.model_construct(raw='', path=tmp_path, root=Path('/'), kind='', data={})
        object.__setattr__(venv, '_recursed', False)
        result = _run(venv.concretize())
        assert result is False
        assert not venv

    def test_sets_finder_name_on_success(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        """After a successful concretize, `finder` holds the name of the winning finder."""
        import myBasis.types.Venv as venv_module  # noqa

        (tmp_path / 'pyvenv.cfg').write_text('home = /usr/bin\nversion = 3.8.12\nprompt = test')

        async def _win_finder(self: Venv) -> Path:
            return tmp_path

        monkeypatch.setattr(venv_module, '_FINDERS', {'winning': _win_finder})
        venv = Venv.model_construct(raw='', path=tmp_path, root=Path('/'), kind='', data={})
        object.__setattr__(venv, '_recursed', False)
        result = _run(venv.concretize())
        assert result is True
        assert venv.finder == 'winning'


############
### UTIL ###
############
async def _async(val: Any) -> Any:
    """Return *val* as a coroutine result, for use with monkeypatch."""
    return val
