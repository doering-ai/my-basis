############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
from typing import Any
import asyncio

### EXTERNAL
import pytest as pyt

### INTERNAL
from myBasis.types.Venv import Venv, Kind, Framework, FRAMEWORKS, RGXS, IS_WINDOWS, MAX_WALK_DEPTH


############
### DATA ###
############
def _run(coro: Any) -> Any:
    """Run a coroutine synchronously."""
    return asyncio.run(coro)


def _make_venv(tmp_path: Path, **kwargs: Any) -> Venv:
    """Construct a Venv with sensible defaults for testing."""
    defaults: dict[str, Any] = dict(
        raw=str(tmp_path),
        origin=tmp_path,
        home=tmp_path,
        root=tmp_path,
        kind=Kind.VENV,
        prompt=tmp_path.name,
        python_version='3.8.12',
        data={},
        window=None,
    )
    defaults.update(kwargs)
    return Venv(**defaults)


############
### BODY ###
############
class TestKind:
    """Tests for the ``Kind`` flag enum."""

    def test_is_flag(self):
        from enum import Flag

        assert issubclass(Kind, Flag)

    def test_none_is_zero(self):
        assert Kind.NONE.value == 0

    def test_members_distinct(self):
        members = [
            Kind.POETRY,
            Kind.HATCH,
            Kind.PDM,
            Kind.RYE,
            Kind.UV,
            Kind.PYENV,
            Kind.PIPENV,
            Kind.VENV,
            Kind.CONDA,
            Kind.IDE,
        ]
        assert len(members) == len(set(members))

    def test_combinable(self):
        combined = Kind.VENV | Kind.CONDA
        assert Kind.VENV in combined
        assert Kind.CONDA in combined

    @pyt.mark.parametrize(
        'name',
        ['POETRY', 'HATCH', 'PDM', 'RYE', 'UV', 'PYENV', 'PIPENV', 'VENV', 'CONDA', 'IDE'],
    )
    def test_member_exists(self, name: str):
        assert hasattr(Kind, name)


class TestFramework:
    """Tests for the ``Framework`` NamedTuple."""

    def test_defaults(self):
        fw = Framework()
        assert fw.cmd == ''
        assert fw.args == ''
        assert fw.file == ''
        assert fw.parent_index == 0
        assert fw.parser is None

    def test_kind_property(self):
        fw = Framework(cmd='hatch')
        assert fw.kind == Kind.HATCH

    def test_kind_property_unknown(self):
        fw = Framework(cmd='unknown_tool')
        assert fw.kind == Kind.NONE

    def test_kind_property_empty(self):
        fw = Framework()
        assert fw.kind == Kind.NONE

    def test_seek_map_item(self):
        result = Framework._seek_map_item('some output\nvenv: /path/to/venv')
        assert result == '/path/to/venv'

    def test_seek_map_item_no_match(self):
        result = Framework._seek_map_item('no venv here')
        assert result == ''


class TestFrameworks:
    """Tests for the ``FRAMEWORKS`` list."""

    def test_nonempty(self):
        assert len(FRAMEWORKS) >= 5

    def test_all_are_framework_instances(self):
        for fw in FRAMEWORKS:
            assert isinstance(fw, Framework)

    def test_contains_hatch(self):
        assert any(fw.cmd == 'hatch' for fw in FRAMEWORKS)

    def test_contains_pdm(self):
        assert any(fw.cmd == 'pdm' for fw in FRAMEWORKS)

    def test_contains_poetry(self):
        assert any(fw.cmd == 'poetry' for fw in FRAMEWORKS)

    def test_contains_pipenv(self):
        assert any(fw.cmd == 'pipenv' for fw in FRAMEWORKS)


class TestVenvBool:
    """Tests for ``Venv.__bool__``."""

    def test_false_when_none_kind(self, tmp_path: Path):
        venv = _make_venv(tmp_path, kind=Kind.NONE)
        assert not venv

    def test_false_when_nonexistent_root(self, tmp_path: Path):
        venv = Venv.model_construct(root=tmp_path / 'nonexistent', kind=Kind.VENV)
        assert not venv

    def test_true_when_valid(self, tmp_path: Path):
        venv = _make_venv(tmp_path)
        assert bool(venv)

    def test_false_when_empty_root(self):
        venv = Venv()
        assert not venv


class TestCleanVersion:
    """Tests for ``Venv.clean_version``."""

    @pyt.mark.parametrize(
        'version, expected',
        [
            ('3.8.12', ('3', '8', '12')),
            ('3.8', ('3', '8', '')),
            ('3', ('3', '', '')),
            ('10.20.300', ('10', '20', '300')),
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

    def test_default_version(self, tmp_path: Path):
        venv = _make_venv(tmp_path, python_version='3.8.12')
        assert venv.clean_version == ('3', '8', '12')


class TestVenvPaths:
    """Tests for cached path properties."""

    def test_bin(self, tmp_path: Path):
        venv = _make_venv(tmp_path)
        expected = tmp_path / ('Scripts' if IS_WINDOWS else 'bin')
        assert venv.bin == expected

    def test_lib(self, tmp_path: Path):
        venv = _make_venv(tmp_path)
        expected = tmp_path / ('Lib' if IS_WINDOWS else 'lib')
        assert venv.lib == expected

    @pyt.mark.parametrize(
        'version, expected_rel',
        [
            ('3.8.12', 'lib/python3.8/site-packages'),
            ('3.10.0', 'lib/python3.10/site-packages'),
            ('3.11', 'lib/python3.11/site-packages'),
        ],
    )
    def test_site_packages(self, tmp_path: Path, version: str, expected_rel: str):
        if IS_WINDOWS:
            expected_rel = 'Lib/site-packages'
        venv = _make_venv(tmp_path, python_version=version)
        assert venv.site_packages == tmp_path / expected_rel


class TestGetPyvenvInfo:
    """Tests for ``Venv.get_pyvenv_info()``."""

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
        (tmp_path / 'pyvenv.cfg').write_text('home = /usr/bin\nversion = 3.8.12\nprompt = test')
        venv = _make_venv(tmp_path)
        result = _run(venv.get_pyvenv_info())
        assert result is not None
        assert set(result.keys()) >= {'home', 'version', 'prompt'}


class TestGetCondaInfo:
    """Tests for ``Venv.get_conda_info()``."""

    def test_returns_none_when_no_conda_meta(self, tmp_path: Path):
        venv = _make_venv(tmp_path)
        result = _run(venv.get_conda_info())
        assert result is None


class TestCheckEnv:
    """Tests for ``Venv.check_env()``."""

    def test_returns_none_when_no_envvars(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.delenv('VIRTUAL_ENV', raising=False)
        monkeypatch.delenv('CONDA_PREFIX', raising=False)
        venv = _make_venv(tmp_path)
        result = _run(venv.check_env())
        assert result is None

    def test_virtual_env(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setenv('VIRTUAL_ENV', str(tmp_path))
        venv = _make_venv(tmp_path)
        result = _run(venv.check_env())
        assert result is not None
        assert venv.kind == Kind.VENV

    def test_conda_prefix(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setenv('CONDA_PREFIX', str(tmp_path))
        venv = _make_venv(tmp_path)
        result = _run(venv.check_env())
        assert result is not None
        assert venv.kind == Kind.CONDA


class TestCheckPath:
    """Tests for ``Venv.check_path()``."""

    def test_finds_venv_directory(self, tmp_path: Path):
        (tmp_path / '.venv').mkdir()
        venv = _make_venv(tmp_path)
        result = _run(venv.check_path())
        assert result == tmp_path / '.venv'
        assert venv.kind == Kind.VENV
        assert venv.home == tmp_path

    def test_finds_venv_named_dir(self, tmp_path: Path):
        (tmp_path / 'venv').mkdir()
        venv = _make_venv(tmp_path)
        result = _run(venv.check_path())
        assert result == tmp_path / 'venv'

    def test_returns_none_when_no_venv(self, tmp_path: Path):
        venv = _make_venv(tmp_path)
        result = _run(venv.check_path())
        assert result is None

    def test_walks_up_to_find_venv(self, tmp_path: Path):
        """check_path walks up parent directories to find a .venv."""
        (tmp_path / '.venv').mkdir()
        sub = tmp_path / 'sub' / 'deep'
        sub.mkdir(parents=True)
        venv = _make_venv(sub)
        result = _run(venv.check_path())
        assert result == tmp_path / '.venv'
        assert venv.home == tmp_path


class TestCheckPathBounds:
    """The ancestor walk in ``check_path`` must be bounded and deterministic."""

    @pyt.fixture(autouse=True)
    def _no_cli_probes(self, monkeypatch: pyt.MonkeyPatch) -> None:
        """Neutralize framework CLI probes so no external tool can answer."""
        monkeypatch.setenv('PATH', '')

    def test_walk_stops_before_home(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        """A .venv sitting in $HOME itself is never picked up from a project below it."""
        home = tmp_path / 'home'
        deep = home / 'projects' / 'app'
        deep.mkdir(parents=True)
        (home / '.venv').mkdir()
        monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
        venv = _make_venv(deep)
        assert _run(venv.check_path()) is None

    def test_walk_outside_home_is_capped(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        """Origins outside $HOME probe at most MAX_WALK_DEPTH ancestors, never the anchor."""
        monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path / 'unrelated'))
        deep = tmp_path.joinpath(*[f'd{i}' for i in range(MAX_WALK_DEPTH + 4)])
        deep.mkdir(parents=True)

        probed: list[Path] = []

        async def spy(self: Venv, path: Path) -> None:
            probed.append(path)
            return None

        monkeypatch.setattr(Venv, '_check_candidate', spy)
        venv = _make_venv(deep)
        assert _run(venv.check_path()) is None
        assert 0 < len(probed) <= MAX_WALK_DEPTH
        assert Path(deep.anchor) not in probed
        assert probed[0] == deep


class TestVenvFind:
    """Tests for ``Venv.find()`` and ``sync_find()``."""

    @pyt.fixture(autouse=True)
    def _isolate(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch) -> None:
        """Confine discovery to ``tmp_path``, away from the developer's real environment.

        Without this, ``check_env`` resolves the repo's own ``.venv`` via ``$VIRTUAL_ENV``
        (which ``uv run`` exports), and ``check_path`` both walks ancestors outside the
        sandbox and probes framework CLIs (``hatch``/``pyenv`` run even without marker
        files) that could resolve environments elsewhere on the machine.
        """
        # `check_env` inspects these before any filesystem search happens.
        monkeypatch.delenv('VIRTUAL_ENV', raising=False)
        monkeypatch.delenv('CONDA_PREFIX', raising=False)
        # `check_path` walks from the origin up to (but excluding) `Path.home()`;
        # pinning home to the parent bounds the candidate list to `tmp_path` itself.
        monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path.parent))
        # Neutralize framework CLI probes so no external tool can answer.
        monkeypatch.setenv('PATH', '')

    def test_short_circuits_when_already_valid(self, tmp_path: Path):
        """A truthy venv returns itself immediately."""
        venv = _make_venv(tmp_path)
        assert bool(venv)
        result = _run(venv.find(tmp_path))
        assert result is venv

    def test_finds_venv_via_find(self, tmp_path: Path):
        (tmp_path / '.venv').mkdir()
        venv = Venv()
        result = _run(venv.find(tmp_path))
        assert bool(result)
        assert result.root == tmp_path / '.venv'

    def test_sync_find(self, tmp_path: Path):
        (tmp_path / '.venv').mkdir()
        venv = Venv()
        result = venv.sync_find(tmp_path)
        assert bool(result)
        assert result.root == tmp_path / '.venv'

    def test_find_no_venv(self, tmp_path: Path):
        venv = Venv()
        result = _run(venv.find(tmp_path))
        assert not bool(result)

    def test_origin_beats_ambient_env(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        """An explicitly-passed origin path wins over an ambient $VIRTUAL_ENV."""
        ambient = tmp_path / 'ambient_env'
        ambient.mkdir()
        origin = tmp_path / 'proj'
        (origin / '.venv').mkdir(parents=True)
        monkeypatch.setenv('VIRTUAL_ENV', str(ambient))

        result = _run(Venv().find(origin))
        assert bool(result)
        assert result.root == origin / '.venv'
        assert result.home == origin
        assert result.kind == Kind.VENV

    def test_ambient_env_is_fallback(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        """$VIRTUAL_ENV is still honored when the origin path yields nothing."""
        ambient = tmp_path / 'ambient_env'
        ambient.mkdir()
        origin = tmp_path / 'proj'
        origin.mkdir()
        monkeypatch.setenv('VIRTUAL_ENV', str(ambient))

        result = _run(Venv().find(origin))
        assert bool(result)
        assert result.root == ambient
        assert result.kind == Kind.VENV


class TestFrameworkProbe:
    """With `exa` fixed, the framework-CLI probing path is live: probe runs *in* the origin."""

    def test_framework_cli_probe_runs_in_candidate_dir(
        self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch
    ):
        """A `hatch` on PATH is consulted with cwd set to the candidate directory."""
        monkeypatch.delenv('VIRTUAL_ENV', raising=False)
        monkeypatch.delenv('CONDA_PREFIX', raising=False)
        monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path.parent))

        # A fake `hatch` that reports the cwd it was invoked from as the env location.
        bin_dir = tmp_path / 'bin'
        bin_dir.mkdir()
        fake_hatch = bin_dir / 'hatch'
        fake_hatch.write_text('#!/bin/sh\npwd\n')
        fake_hatch.chmod(0o755)
        monkeypatch.setenv('PATH', str(bin_dir))

        origin = tmp_path / 'proj'
        origin.mkdir()
        venv = _make_venv(origin, kind=Kind.NONE)
        result = _run(venv.check_path())
        assert result is not None
        assert Path(result).resolve() == origin.resolve(), 'probe must run with cwd=origin'
        assert venv.kind == Kind.HATCH
        assert venv.home == origin


class TestExactMatch:
    """Tests for ``Venv.exact_match``."""

    def test_true_when_home_equals_origin(self, tmp_path: Path):
        venv = _make_venv(tmp_path, home=tmp_path, origin=tmp_path)
        assert venv.exact_match

    def test_false_when_home_differs_from_origin(self, tmp_path: Path):
        other = tmp_path / 'other'
        other.mkdir()
        venv = _make_venv(tmp_path, home=other, origin=tmp_path)
        assert not venv.exact_match


class TestVenvRegexes:
    """Tests for the RGXS dict in Venv."""

    def test_has_finder_detritus(self):
        assert 'finder_detritus' in RGXS

    def test_has_version(self):
        assert 'version' in RGXS

    def test_has_venv_map_item(self):
        assert 'venv_map_item' in RGXS

    def test_version_matches_standard(self):
        assert RGXS['version'].search('3.8.12')
        assert RGXS['version'].search('Python 3.9.7')

    def test_venv_map_item_matches(self):
        assert RGXS['venv_map_item'].search('venv: /path/to/venv')
        assert RGXS['venv_map_item'].search('venv = /path/to/venv')
