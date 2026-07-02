############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar

### EXTERNAL
import pytest as pyt
import pydantic as pyd
import sublime as sb

### INTERNAL
from myBasis.types.PackageSettings import PackageSettings


############
### BODY ###
############
class TestPackageSettingsConstruction:
    """Tests for ``PackageSettings`` subclassing and registration."""

    def test_requires_pkg_classvar(self):
        with pyt.raises(TypeError, match='PKG'):

            class _BadSettings(PackageSettings):
                pass

    def test_duplicate_pkg_raises(self):
        """__init_subclass__ checks _REGISTRY for duplicates but doesn't register there itself.

        Registration only happens in ``new()``, so defining two classes with the same PKG
        does not raise unless ``new()`` was called for the first one.
        """

        # The first class is fine
        class _Settings1(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_dup_check'

        # Since __init_subclass__ doesn't add to _REGISTRY, a second class with the same
        # PKG also succeeds at class-definition time
        class _Settings2(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_dup_check'

        # Both can be defined without error
        assert _Settings1.PKG == _Settings2.PKG

    def test_subclass_with_pkg(self):
        class _Settings(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_ok'
            debug: bool = False

        assert _Settings.PKG == 'test_pkg_ok'

    def test_is_pydantic_model(self):
        assert issubclass(PackageSettings, pyd.BaseModel)

    def test_debug_field_default(self):
        class _Settings(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_debug'
            debug: bool = False

        inst = _Settings()
        assert inst.debug is False


class TestPackageSettingsNormKey:
    """Tests for ``normkey``."""

    def test_simple_key(self):
        result = PackageSettings.normkey('debug')
        assert result == 'debug'

    def test_dotted_key(self):
        result = PackageSettings.normkey('my.package.debug')
        assert '.' in result

    def test_strips_quotes(self):
        result = PackageSettings.normkey('"debug"')
        assert result == 'debug'

    def test_caches(self):
        """normkey uses lru_cache."""
        r1 = PackageSettings.normkey('cached_key')
        r2 = PackageSettings.normkey('cached_key')
        assert r1 == r2


class TestPackageSettingsKeys:
    """Tests for ``keys`` and ``normkeys``."""

    def test_keys_returns_field_names(self):
        class _Settings(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_keys'
            debug: bool = False
            level: int = 1

        assert 'debug' in _Settings.keys()
        assert 'level' in _Settings.keys()

    def test_normkeys_returns_normalized(self):
        class _Settings(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_normkeys'
            debug: bool = False

        normkeys = _Settings.normkeys()
        assert isinstance(normkeys, set)
        assert 'debug' in normkeys


class TestPackageSettingsFilename:
    """Tests for ``filename``."""

    def test_filename(self):
        class _Settings(PackageSettings):
            PKG: ClassVar[str] = 'my_test_pkg'

        assert _Settings.filename() == 'my_test_pkg.sublime-settings'


class TestPackageSettingsNew:
    """Tests for ``PackageSettings.new``."""

    def test_new_caches_in_registry(self):
        class _Settings(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_new'
            debug: bool = False

        # Create with mock settings
        settings = sb.load_settings('test_pkg_new.sublime-settings')
        inst = _Settings.new(settings)
        assert isinstance(inst, _Settings)
        # Second call returns cached
        inst2 = _Settings.new()
        assert inst2 is inst
