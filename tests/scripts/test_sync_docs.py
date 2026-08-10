############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
from my import PATHS
from my.scripts.sync_docs import Tool, main


############
### DATA ###
############
SKIPPED_PACKAGES = ('_adoption', 'infra', 'scripts', 'templates', 'text', 'type')


############
### BODY ###
############
class TestSyncDocs:
    """Smoke tests for the `sync-docs` console script."""

    @pyt.mark.parametrize(
        'package, init_text, expected',
        [
            pyt.param(
                'widgets',
                '"""Widget utilities.\n\nSome more prose.\n"""\n',
                ('widgets', 'would be updated'),
                id='update',
            ),
            pyt.param(
                'undocumented',
                '# no module docstring here\n',
                ('0 package(s) would be updated.',),
                id='no-changes',
            ),
        ],
    )
    def test_main__dry_run(
        self,
        tmp_path: Path,
        capsys: pyt.CaptureFixture,
        package: str,
        init_text: str,
        expected: tuple[str, ...],
    ):
        """Dry runs report pending or absent changes without writing documentation."""
        pkg_dir = tmp_path / 'my' / package
        pkg_dir.mkdir(parents=True)
        (tmp_path / 'my' / '__init__.py').write_text('"""Top-level, excluded from sync."""\n')
        (pkg_dir / '__init__.py').write_text(init_text)

        main('--dry', str(tmp_path))

        out = capsys.readouterr().out
        assert all(text in out for text in expected)
        assert not (tmp_path / 'docs').exists()

    @pyt.mark.parametrize('package', SKIPPED_PACKAGES)
    def test_main__skips_internal(self, tmp_path: Path, package: str):
        """Internal implementation packages never generate public API pages."""
        assert frozenset(SKIPPED_PACKAGES) == Tool.SKIP
        pkg_dir = tmp_path / 'my' / package
        pkg_dir.mkdir(parents=True)
        (tmp_path / 'my' / '__init__.py').write_text('"""Public package."""\n')
        (pkg_dir / '__init__.py').write_text('"""Internal package."""\n')

        main(str(tmp_path))

        assert not (tmp_path / 'docs' / f'{package}.md').exists()


class TestPackageDiscovery:
    """The documented package comes from pyproject.toml, `--package`, or the legacy `my`."""

    @staticmethod
    def _make_pkg(root: Path, package: str, sub: str = 'widgets') -> None:
        pkg_dir = root / package / sub
        pkg_dir.mkdir(parents=True)
        (root / package / '__init__.py').write_text(f'"""The {package} package."""\n')
        (pkg_dir / '__init__.py').write_text('"""Widget utilities.\n\nSome more prose.\n"""\n')

    @pyt.mark.parametrize(
        'module_name',
        [
            pyt.param('"means"', id='string-form'),
            pyt.param('["means"]', id='list-form'),
        ],
    )
    def test_discovers_from_pyproject(self, tmp_path: Path, module_name: str):
        """`[tool.uv.build-backend] module-name` names the documented package."""
        (tmp_path / 'pyproject.toml').write_text(
            f'[tool.uv.build-backend]\nmodule-name = {module_name}\n'
        )
        self._make_pkg(tmp_path, 'means')

        main(str(tmp_path))

        page = tmp_path / 'docs' / 'widgets.md'
        assert page.exists()
        assert '# `means.widgets`: Widget utilities' in page.read_text()

    def test_explicit_package_overrides_pyproject(self, tmp_path: Path):
        """An explicit `--package` always wins over pyproject discovery."""
        (tmp_path / 'pyproject.toml').write_text(
            '[tool.uv.build-backend]\nmodule-name = ["means", "extra"]\n'
        )
        self._make_pkg(tmp_path, 'other')

        main('--package', 'other', str(tmp_path))

        page = tmp_path / 'docs' / 'widgets.md'
        assert page.exists()
        assert '# `other.widgets`: Widget utilities' in page.read_text()

    def test_legacy_my_fallback(self, tmp_path: Path):
        """Without pyproject.toml, a top-level `my` package keeps the old default."""
        self._make_pkg(tmp_path, 'my')

        main(str(tmp_path))

        page = tmp_path / 'docs' / 'widgets.md'
        assert page.exists()
        assert '# `my.widgets`: Widget utilities' in page.read_text()

    @pyt.mark.parametrize(
        'args, pyproject, expected',
        [
            pyt.param(
                ('--package', 'missing'),
                '',
                ('--package', 'missing', '__init__.py'),
                id='explicit-missing',
            ),
            pyt.param(
                (),
                '[tool.uv.build-backend]\nmodule-name = "means"\n',
                ('module-name', 'means', '__init__.py'),
                id='discovered-missing',
            ),
            pyt.param(
                (),
                '',
                ('--package',),
                id='undiscoverable',
            ),
        ],
    )
    def test_invalid_configuration_exits_2(
        self,
        tmp_path: Path,
        capsys: pyt.CaptureFixture,
        args: tuple[str, ...],
        pyproject: str,
        expected: tuple[str, ...],
    ):
        """Package configuration failures exit 2 with one concise stderr error."""
        if pyproject:
            (tmp_path / 'pyproject.toml').write_text(pyproject)

        with pyt.raises(SystemExit) as raised:
            main(*args, str(tmp_path))

        captured = capsys.readouterr()
        assert raised.value.code == 2
        assert captured.out == ''
        assert captured.err.count('\n') == 1
        assert 'Traceback' not in captured.err
        assert all(fragment in captured.err for fragment in expected)

    def test_multi_package_discovery_requires_explicit_package(
        self,
        tmp_path: Path,
        capsys: pyt.CaptureFixture,
    ):
        """Ambiguous module-name lists fail closed before documentation is changed."""
        (tmp_path / 'pyproject.toml').write_text(
            '[tool.uv.build-backend]\nmodule-name = ["alpha", "beta"]\n'
        )
        self._make_pkg(tmp_path, 'alpha')
        self._make_pkg(tmp_path, 'beta')

        with pyt.raises(SystemExit) as raised:
            main(str(tmp_path))

        captured = capsys.readouterr()
        assert raised.value.code == 2
        assert captured.out == ''
        assert captured.err.count('\n') == 1
        assert 'multiple packages' in captured.err
        assert '--package' in captured.err
        assert not (tmp_path / 'docs').exists()

    def test_explicit_root_skips_ancestor_discovery(
        self,
        tmp_path: Path,
        monkeypatch: pyt.MonkeyPatch,
    ):
        """An explicit root never consults ancestor project discovery."""
        self._make_pkg(tmp_path, 'my')

        def fail_discovery(_filesystem: object) -> None:
            raise AssertionError('ancestor discovery should not run')

        monkeypatch.setattr(type(PATHS), 'seek_project', fail_discovery)

        main('--dry', str(tmp_path))

    def test_help_skips_ancestor_discovery(
        self,
        monkeypatch: pyt.MonkeyPatch,
        capsys: pyt.CaptureFixture,
    ):
        """Help exits successfully without consulting ancestor project discovery."""

        def fail_discovery(_filesystem: object) -> None:
            raise AssertionError('ancestor discovery should not run')

        monkeypatch.setattr(type(PATHS), 'seek_project', fail_discovery)

        with pyt.raises(SystemExit) as raised:
            main('--help')

        assert raised.value.code == 0
        assert 'usage:' in capsys.readouterr().out

    def test_handwritten_page_is_never_rewritten(self, tmp_path: Path, capsys: pyt.CaptureFixture):
        """A docs page without a {toctree} block is hand-written and left untouched."""
        self._make_pkg(tmp_path, 'my')
        guide = tmp_path / 'docs' / 'widgets.md'
        guide.parent.mkdir(parents=True)
        guide.write_text('# A Hand-Written Guide\n\nProse the author maintains by hand.\n')

        main(str(tmp_path))

        assert (
            guide.read_text() == '# A Hand-Written Guide\n\nProse the author maintains by hand.\n'
        )
        assert 'SKIP' in capsys.readouterr().out
