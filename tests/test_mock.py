############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
import sys

### EXTERNAL
import pytest as pyt

### INTERNAL
import myBasis
from myBasis.infra import mock
from myBasis.infra.mock import _sublime


############
### BODY ###
############
class TestIsLive:
    """`IS_LIVE` must be True ONLY inside a real Sublime Text process."""

    def test_false_under_mocks(self):
        """The test suite runs on the mock modules, so IS_LIVE must report False."""
        assert mock.IS_LIVE is False

    def test_reexport_matches(self):
        assert myBasis.IS_LIVE is mock.IS_LIVE

    def test_mock_module_is_installed(self):
        """Sanity: sys.modules['sublime'] is the mock (external mode), not a live ST."""
        assert getattr(sys.modules['sublime'], 'MODE', 'internal') == 'external'

    def test_install_is_idempotent_and_keeps_is_live_false(self):
        """Re-running install() must neither crash nor flip IS_LIVE to True."""
        mock.install()
        mock.install()
        assert mock.IS_LIVE is False
        assert sys.modules['sublime'] is _sublime


class TestInferPaths:
    """Tests for ``mock._sublime.infer_paths`` root validation."""

    def test_valid_st_root(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setenv('ST_ROOT', str(tmp_path))
        _home, _cache, root = _sublime.infer_paths()
        assert root == tmp_path.resolve()

    def test_invalid_st_root_raises(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        """A nonexistent $ST_ROOT must be rejected, not silently returned."""
        monkeypatch.setenv('ST_ROOT', str(tmp_path / 'nonexistent'))
        with pyt.raises(ValueError, match='ST_ROOT'):
            _sublime.infer_paths()
