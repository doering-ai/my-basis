############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
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
        (tmp_path / 'pyproject.toml').write_text('[tool.uv.build-backend]\nmodule-name = "means"\n')
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

    def test_undiscoverable_package_raises(self, tmp_path: Path):
        """A project with no pyproject module-name and no `my` package fails loudly."""
        with pyt.raises(ValueError, match='--package'):
            main(str(tmp_path))
