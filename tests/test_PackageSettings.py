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
        """Defining two settings classes with the same PKG raises at class-definition time."""

        # The first class is fine
        class _Settings1(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_dup_check'

        assert _Settings1.PKG == 'test_pkg_dup_check'

        # A second class claiming the same PKG must be rejected immediately
        with pyt.raises(TypeError, match='already registered'):

            class _Settings2(PackageSettings):
                PKG: ClassVar[str] = 'test_pkg_dup_check'

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


class TestPackageSettingsOpen:
    """Regression tests for ``PackageSettings.open`` (contextmanager/classmethod order)."""

    def test_open_is_usable_as_a_context_manager(self):
        """``open()`` must be invokable directly on the class and bind ``cls`` correctly.

        Guards against the decorator-order bug where ``@ctx.contextmanager`` was stacked above
        ``@classmethod``: contextmanager wrapped the classmethod descriptor itself, so ``cls``
        never bound and ``SomeSettings.open()`` raised at call time instead of entering the
        context manager.
        """

        class _Settings(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_open'
            debug: bool = False

        with _Settings.open() as inst:
            assert isinstance(inst, _Settings)

    def test_open_yields_the_registered_instance(self):
        """The yielded object is the same instance the class registry already holds."""

        class _Settings(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_open_yield'
            debug: bool = False

        expected = _Settings.new()
        with _Settings.open() as inst:
            assert inst is expected
            assert inst.debug is False

    def test_open_across_subclasses_binds_the_correct_cls(self):
        """Two subclasses opened in sequence must each yield their own class's instance.

        A broken binding (``cls`` failing to resolve, or resolving to the wrong class) would be
        masked if only one subclass were ever exercised.
        """

        class _SettingsA(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_open_a'
            debug: bool = False

        class _SettingsB(PackageSettings):
            PKG: ClassVar[str] = 'test_pkg_open_b'
            debug: bool = False

        with _SettingsA.open() as inst_a:
            assert isinstance(inst_a, _SettingsA)
            assert not isinstance(inst_a, _SettingsB)

        with _SettingsB.open() as inst_b:
            assert isinstance(inst_b, _SettingsB)
            assert not isinstance(inst_b, _SettingsA)


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
