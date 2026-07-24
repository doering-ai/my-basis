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
