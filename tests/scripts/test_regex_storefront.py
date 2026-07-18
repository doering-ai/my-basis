############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path

### EXTERNAL
import regex
import pytest as pyt

### INTERNAL
from my.scripts.regex_storefront import Storefront

cls = Storefront


############
### BODY ###
############
class TestStorefront:
    """Smoke tests for the `regex-storefront` console script."""

    def test_construct(self):
        # Regression: the `store` field defaulted to a shared RegexStore instance, which pydantic
        # deep-copied on every construction and choked on its threading.Lock. A default_factory
        # fixes it; this guards against the mutable-default re-creeping in.
        store = cls(actions=['condense'])
        assert store.actions == ['condense']

    def test_condense__builds_matching_branch(self, tmp_path: Path):
        words = ['numpy', 'np', 'pandas', 'pd', 'plt', 'utils']
        src = tmp_path / 'words.txt'
        src.write_text('\n'.join(words))
        dst = tmp_path / 'out.txt'

        store = cls(actions=['condense'], source=src, target=dst)
        list(store.execute_all())

        pattern = dst.read_text().strip()
        rgx = regex.compile(pattern)
        # Every input word is matched by the condensed branch, and a non-member is not.
        assert all(rgx.fullmatch(w) for w in words)
        assert not rgx.fullmatch('definitely_not_a_module')

    def test_condense__requires_source_and_target(self):
        store = cls(actions=['condense'])
        with pyt.raises(AssertionError):
            list(store.execute_all())
