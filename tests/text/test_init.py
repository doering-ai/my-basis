############
### HEAD ###
############
### STANDARD
import warnings

### EXTERNAL
import pytest as pyt

### INTERNAL
with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import my.text as text
from my.regex.RegexStore import RegexStore


############
### BODY ###
############
class TestTextShim:
    # -------------------
    # `.` Initial Methods
    # -------------------
    def test_import__emits_deprecation_warning(self):
        # Force a fresh import to observe the warning (module is already cached from HEAD).
        import importlib
        import sys

        sys.modules.pop('my.text', None)
        with pyt.warns(DeprecationWarning, match='my.text is deprecated'):
            importlib.import_module('my.text')

    # -------------------
    # `+` Primary Methods
    # -------------------
    def test_atom__aliases_regexstore_atom(self):
        # basis-12 item 3: `atom` DOES have a modern counterpart (`RegexStore.atom`, added
        # 2026-01-29) -- the shim previously omitted it entirely, claiming no equivalent existed.
        assert text.atom is RegexStore.atom
        assert 'atom' in text.__all__

    @pyt.mark.parametrize(
        'contents',
        [
            ('hello',),
            (['a', 'b'],),
            ('x', 'y'),
        ],
    )
    def test_atom__matches_regexstore_behavior(self, contents: tuple):
        assert text.atom(*contents) == RegexStore.atom(*contents)
