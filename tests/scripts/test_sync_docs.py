############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.scripts.sync_docs import main


############
### BODY ###
############
class TestSyncDocs:
    """Smoke tests for the `sync-docs` console script."""

    def test_main__dry_run_does_not_crash_or_write(
        self, tmp_path: Path, capsys: pyt.CaptureFixture
    ):
        """`sync-docs --dry` runs end-to-end against a synthetic project without writing files.

        basis-T1 item 4: `[project.scripts]` only declares `sync-docs = "my.scripts.sync_docs:
        main"` -- unlike `regex-storefront` (see `test_regex_storefront.py`), it had no coverage
        at all. Mirrors that file's pattern: build a minimal synthetic project under `tmp_path`
        and drive `main()` directly (its `*vargs` signature takes explicit args, so this bypasses
        `sys.argv` entirely -- safe under pytest). `--dry` is the harmless mode: it prints a diff
        summary but never touches `docs/`.
        """
        pkg_dir = tmp_path / 'my' / 'widgets'
        pkg_dir.mkdir(parents=True)
        (tmp_path / 'my' / '__init__.py').write_text('"""Top-level, excluded from sync."""\n')
        (pkg_dir / '__init__.py').write_text('"""Widget utilities.\n\nSome more prose.\n"""\n')

        main('--dry', str(tmp_path))

        out = capsys.readouterr().out
        assert 'widgets' in out
        assert 'would be updated' in out
        assert not (tmp_path / 'docs').exists()

    def test_main__dry_run_no_changes_needed(self, tmp_path: Path, capsys: pyt.CaptureFixture):
        """A package with no `__init__.py` docstring is skipped, not treated as an update."""
        pkg_dir = tmp_path / 'my' / 'undocumented'
        pkg_dir.mkdir(parents=True)
        (pkg_dir / '__init__.py').write_text('# no module docstring here\n')

        main('--dry', str(tmp_path))

        out = capsys.readouterr().out
        assert '0 package(s) would be updated.' in out
        assert not (tmp_path / 'docs').exists()
