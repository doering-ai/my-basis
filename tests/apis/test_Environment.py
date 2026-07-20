############
### HEAD ###
############
### STANDARD
from pathlib import Path
import collections.abc as abc
import os

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.apis import Environment
from ..conftest import boolmap, Patch

cls = Environment


############
### BODY ###
############
class TestEnvironment:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.fixture(autouse=True)
    def _isolate_environ(self) -> abc.Iterator[None]:
        """Snapshot and restore the `_ENVIRON` singleton classvar around every test.

        basis-T3 regression: `temp_env_var` uses `patch.setitem`, which monkeypatch reverts
        automatically -- but `test_set`, `test_setattr`, `test_setitem`, and
        `test_set__clears_cache_for_previously_unset_key` call `Environment.set()`/
        `__setattr__`/`__setitem__` directly, writing straight into the shared classvar dict
        with no teardown at all. Confirmed empirically: running this file alone leaves
        `NEW_VAR`, `SETATTR_TEST`, `SETITEM_TEST`, and `NEVER_BEFORE_SET_KEY` permanently
        present in `Environment._ENVIRON` afterward, for the rest of the pytest session. This
        autouse fixture restores the pre-test snapshot (and clears the three lookup caches)
        regardless of which path a test used to mutate state.
        """
        snapshot = dict(cls._ENVIRON)
        yield
        cls._ENVIRON.clear()
        cls._ENVIRON.update(snapshot)
        cls._get.cache_clear()
        cls._path.cache_clear()
        cls._flag.cache_clear()

    @pyt.fixture
    def env_instance(self, patch: Patch) -> Environment:
        """Create a fresh Environment instance with clean state."""
        # Clear any caches before tests
        cls._get.cache_clear()
        cls._path.cache_clear()
        cls._flag.cache_clear()
        return cls()

    @pyt.fixture
    def temp_env_var(self, patch: Patch):
        """Fixture to temporarily set environment variables."""

        def _set_var(key: str, value: str):
            patch.setitem(cls._ENVIRON, key, value)
            cls._get.cache_clear()
            cls._path.cache_clear()
            cls._flag.cache_clear()

        return _set_var

    def test_str(self, env_instance: Environment):
        """Test that __str__ hides sensitive information."""
        assert str(env_instance) == 'Environment(...)'

    def test_repr(self, env_instance: Environment):
        """Test that __repr__ hides sensitive information."""
        assert repr(env_instance) == 'Environment(...)'

    # -------------------
    # `-` Private Methods
    # -------------------
    # (These are tested implicitly through public methods)

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'key, value, expected',
        [
            ('TEST_VAR', 'simple_value', 'simple_value'),
            ('EMPTY_VAR', '', ''),
            ('NUMERIC_VAR', '12345', '12345'),
            ('MISSING_VAR', None, ''),
        ],
    )
    def test_get(
        self, env_instance: Environment, temp_env_var, key: str, value: str | None, expected: str
    ):
        """Test basic environment variable retrieval."""
        if value is not None:
            temp_env_var(key, value)

        result = env_instance.get(key)
        assert result == expected

    @pyt.mark.parametrize(
        'key, default, expected',
        [
            ('MISSING_KEY', 'default_value', 'default_value'),
            ('MISSING_KEY', '', ''),
            ('MISSING_KEY', 'fallback', 'fallback'),
        ],
    )
    def test_get__with_default(
        self, env_instance: Environment, key: str, default: str, expected: str
    ):
        """Test get method with default values."""
        result = env_instance.get(key, default)
        assert result == expected

    @pyt.mark.parametrize(
        'var_value, expected',
        [
            ('$HOME', os.environ.get('HOME', '')),
            ('${HOME}', os.environ.get('HOME', '')),
            ('prefix_$HOME', f'prefix_{os.environ.get("HOME", "")}'),
            ('${HOME}_suffix', f'{os.environ.get("HOME", "")}_suffix'),
            ('no_vars_here', 'no_vars_here'),
        ],
    )
    def test_get__interpolation(
        self, env_instance: Environment, temp_env_var, var_value: str, expected: str
    ):
        """Test variable interpolation in environment values."""
        temp_env_var('TEST_INTERPOLATION', var_value)
        result = env_instance.get('TEST_INTERPOLATION')
        assert result == expected

    def test_set(self, env_instance: Environment):
        """Test setting environment variables."""
        env_instance.set('NEW_VAR', 'test_value')
        assert cls._ENVIRON['NEW_VAR'] == 'test_value'
        # Clear cache to ensure fresh read
        cls._get.cache_clear()
        assert env_instance.get('NEW_VAR') == 'test_value'

    def test_set__clears_caches_on_change(self, env_instance: Environment, temp_env_var):
        """Test that changing a value clears all caches."""
        temp_env_var('CACHE_TEST', 'initial')
        _ = env_instance.get('CACHE_TEST')

        # Change the value - should clear caches
        env_instance.set('CACHE_TEST', 'updated')
        assert env_instance.get('CACHE_TEST') == 'updated'

    def test_set__no_cache_clear_if_same(self, env_instance: Environment, temp_env_var):
        """Test that setting the same value doesn't clear caches."""
        temp_env_var('SAME_VAR', 'value')
        env_instance.set('SAME_VAR', 'value')  # Should not clear caches
        assert env_instance.get('SAME_VAR') == 'value'

    def test_set__clears_cache_for_previously_unset_key(self, env_instance: Environment):
        """Regression: `set()` must clear the cache for a key that was never set before.

        A key absent from `_ENVIRON` reads back as `''` (falsy), so the old
        `if cur := self.get(key):` guard skipped the cache-clear whenever the key being
        set had no prior value -- the cached `''` stuck around forever even though
        `_ENVIRON` held the freshly-set value underneath it.
        """
        assert env_instance.get('NEVER_BEFORE_SET_KEY') == ''  # populates the `_get` cache
        env_instance.set('NEVER_BEFORE_SET_KEY', 'now_set')
        assert env_instance.get('NEVER_BEFORE_SET_KEY') == 'now_set'

    @pyt.mark.parametrize(
        'invalid_key',
        [
            'lowercase',
            'Mixed_Case',
            'has-dash',
            'has space',
            'has.dot',
            '',
        ],
    )
    def test_set__validates_name(self, env_instance: Environment, invalid_key: str):
        """Test that set validates environment variable names."""
        with pyt.raises(AssertionError):
            env_instance.set(invalid_key, 'value')

    @pyt.mark.parametrize(
        'key, value, default',
        [
            ('PATH_VAR', '~/test', Path.home() / 'test'),
            ('PATH_VAR', '/absolute/path', Path('/absolute/path')),
            ('PATH_VAR', '.', Path.cwd()),
        ],
    )
    def test_path(
        self, env_instance: Environment, temp_env_var, key: str, value: str, default: Path
    ):
        """Test path coercion and expansion."""
        temp_env_var(key, value)
        result = env_instance.path(key)
        assert isinstance(result, Path)
        assert result == default.resolve()

    def test_path__with_interpolation(self, env_instance: Environment, temp_env_var):
        """Test path with variable interpolation."""
        temp_env_var('BASE_PATH', '/base')
        temp_env_var('NESTED_PATH', '$BASE_PATH/nested')

        result = env_instance.path('NESTED_PATH')
        assert result == Path('/base/nested')

    def test_path__with_mkdir(self, env_instance: Environment, temp_env_var, tmp_path: Path):
        """Test path creation with mkdir option."""
        new_dir = tmp_path / 'new_directory'
        temp_env_var('NEW_DIR', str(new_dir))

        result = env_instance.path('NEW_DIR', mkdir=True)
        assert result.exists()
        assert result.is_dir()

    def test_path__with_default(self, env_instance: Environment):
        """Test path method with default value."""
        result = env_instance.path('NONEXISTENT_PATH', default='/default/path')
        assert result == Path('/default/path')

    @pyt.mark.parametrize(
        'key, value, expected',
        [
            ('FLAG_INT', '42', 42),
            ('FLAG_NEGATIVE', '-10', -10),
            ('FLAG_ZERO', '0', 0),
            ('FLAG_TRUE', 'true', 1),
            ('FLAG_TRUE', 'True', 1),
            ('FLAG_TRUE', 't', 1),
            ('FLAG_TRUE', 'T', 1),
            ('FLAG_YES', 'yes', 1),
            ('FLAG_YES', 'y', 1),
            ('FLAG_YES', 'Y', 1),
            ('FLAG_ENABLE', 'enable', 1),
            ('FLAG_ENABLED', 'enabled', 1),
            ('FLAG_ON', 'on', 1),
            ('FLAG_ON', 'ON', 1),
            ('FLAG_FALSE', 'false', 0),
            ('FLAG_FALSE', 'no', 0),
            ('FLAG_FALSE', 'random_string', 0),
            ('FLAG_EMPTY', '', 0),
        ],
    )
    def test_flag(
        self, env_instance: Environment, temp_env_var, key: str, value: str, expected: int
    ):
        """Test flag coercion for various input formats."""
        temp_env_var(key, value)
        result = env_instance.flag(key)
        assert result == expected

    def test_flag__with_default(self, env_instance: Environment):
        """Test flag method with default value."""
        result = env_instance.flag('NONEXISTENT_FLAG', default=99)
        assert result == 99

    @pyt.mark.parametrize(
        'invalid_key',
        [
            '',
            'lowercase',
        ],
    )
    def test_flag__validates_uppercase(
        self, env_instance: Environment, temp_env_var, invalid_key: str
    ):
        """Test that flag validates uppercase requirement."""
        if invalid_key:
            temp_env_var(invalid_key, 'value')

        with pyt.raises(AssertionError):
            env_instance.flag(invalid_key)

    @pyt.mark.parametrize(
        'val, expected',
        [
            ('${HOME}', os.environ.get('HOME', '')),
            ('$HOME', os.environ.get('HOME', '')),
            ('prefix_${HOME}_suffix', f'prefix_{os.environ.get("HOME", "")}_suffix'),
            ('$HOME/data/$USER', f'{os.environ.get("HOME", "")}/data/{os.environ.get("USER", "")}'),
            ('no_interpolation', 'no_interpolation'),
            ('', ''),
        ],
    )
    def test_interpolate(self, val: str, expected: str):
        """Test static interpolate method."""
        result = cls.interpolate(val)
        assert result == expected

    def test_interpolate__nested(self, env_instance: Environment, temp_env_var):
        """Test nested variable interpolation."""
        temp_env_var('VAR_A', 'value_a')
        temp_env_var('VAR_B', '$VAR_A/extended')

        result = cls.interpolate('$VAR_B')
        assert result == 'value_a/extended'

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    def test_getattr(self, env_instance: Environment, temp_env_var):
        """Test __getattr__ for attribute-style access."""
        temp_env_var('ATTR_TEST', 'attr_value')
        assert env_instance.ATTR_TEST == 'attr_value'

    def test_getitem(self, env_instance: Environment, temp_env_var):
        """Test __getitem__ for dict-style access."""
        temp_env_var('ITEM_TEST', 'item_value')
        assert env_instance['ITEM_TEST'] == 'item_value'

    def test_setattr(self, env_instance: Environment):
        """Test __setattr__ for attribute-style setting."""
        env_instance.SETATTR_TEST = 'new_value'
        assert cls._ENVIRON['SETATTR_TEST'] == 'new_value'

    def test_setitem(self, env_instance: Environment):
        """Test __setitem__ for dict-style setting."""
        env_instance['SETITEM_TEST'] = 'new_value'
        assert cls._ENVIRON['SETITEM_TEST'] == 'new_value'

    @pyt.mark.parametrize(
        'key, exists',
        boolmap(
            true=['HOME', 'PATH'],
            false=['NONEXISTENT_KEY_12345', 'MISSING_VAR'],
        ),
    )
    def test_contains(self, env_instance: Environment, key: str, exists: bool):
        """Test __contains__ for membership testing."""
        assert (key in env_instance) == exists

    # ---------------
    # `*1` Properties
    # ---------------
    def test_paths_property(self, env_instance: Environment, temp_env_var):
        """Test paths property for dot-notation access."""
        temp_env_var('TEST_PATH', '~/test')
        result = env_instance.paths.TEST_PATH
        assert isinstance(result, Path)
        assert result == (Path.home() / 'test').resolve()

    def test_paths_property__cached(self, env_instance: Environment):
        """Test that paths property is cached."""
        paths1 = env_instance.paths
        paths2 = env_instance.paths
        assert paths1 is paths2

    def test_flags_property(self, env_instance: Environment, temp_env_var):
        """Test flags property for dot-notation access."""
        temp_env_var('TEST_FLAG', '42')
        result = env_instance.flags.TEST_FLAG
        assert result == 42

    def test_flags_property__cached(self, env_instance: Environment):
        """Test that flags property is cached."""
        flags1 = env_instance.flags
        flags2 = env_instance.flags
        assert flags1 is flags2

    @pyt.mark.parametrize(
        'mode_value, expected',
        [
            ('dev', True),
            ('development', True),
            ('DEV', True),
            ('prod', False),
            ('production', False),
            ('test', False),
            ('', True),  # Default is 'dev'
        ],
    )
    def test_is_dev(self, env_instance: Environment, temp_env_var, mode_value: str, expected: bool):
        """Test is_dev property."""
        if mode_value:
            temp_env_var('MY_MODE', mode_value)
        else:
            # Clear MY_MODE if it exists
            if 'MY_MODE' in cls._ENVIRON:
                del cls._ENVIRON['MY_MODE']
            cls._get.cache_clear()

        assert env_instance.is_dev == expected

    # ------------
    # `*2` Methods
    # ------------
    @pyt.mark.parametrize(
        'key, expected',
        boolmap(
            true=[
                'VALID_NAME',
                'ANOTHER_VALID_123',
                '_LEADING_UNDERSCORE',
                'TRAILING_UNDERSCORE_',
                'MULTIPLE___UNDERSCORES',
                'NUMBER_123_END',
                '_123',
            ],
            false=[
                'lowercase',
                'Mixed_Case',
                'has-dash',
                'has space',
                'has.dot',
                'has@symbol',
                '',
            ],
        ),
    )
    def test_is_valid_name(self, key: str, expected: bool):
        """Test is_valid_name static method."""
        assert cls.is_valid_name(key) == expected

    @pyt.mark.parametrize(
        'valid_key',
        [
            'VALID_NAME',
            'ANOTHER_VALID_123',
            '_LEADING',
            'TRAILING_',
        ],
    )
    def test_validate_name__valid(self, valid_key: str):
        """Test validate_name with valid keys."""
        cls.validate_name(valid_key)  # Should not raise

    @pyt.mark.parametrize(
        'invalid_key',
        [
            'lowercase',
            'Mixed_Case',
            'has-dash',
            '',
        ],
    )
    def test_validate_name__invalid(self, invalid_key: str):
        """Test validate_name with invalid keys."""
        with pyt.raises(AssertionError):
            cls.validate_name(invalid_key)

    # ----------------
    # Edge Cases Tests
    # ----------------
    def test_flag__as_boolean(self, env_instance: Environment, temp_env_var):
        """Test that flags work correctly with bool() coercion."""
        temp_env_var('BOOL_TRUE', 'yes')
        temp_env_var('BOOL_FALSE', '')
        temp_env_var('BOOL_ZERO', '0')
        temp_env_var('BOOL_NONZERO', '42')

        assert bool(env_instance.flags.BOOL_TRUE)
        assert not bool(env_instance.flags.BOOL_FALSE)
        assert not bool(env_instance.flags.BOOL_ZERO)
        assert bool(env_instance.flags.BOOL_NONZERO)

    def test_path__empty_string(self, env_instance: Environment, temp_env_var):
        """Test path coercion with empty string."""
        temp_env_var('EMPTY_PATH', '')
        result = env_instance.path('EMPTY_PATH')
        assert isinstance(result, Path)

    def test_path__mkdir_with_empty_value(self, env_instance: Environment, temp_env_var):
        """Test that mkdir=True with empty value doesn't create directories."""
        temp_env_var('EMPTY_PATH', '')
        result = env_instance.path('EMPTY_PATH', mkdir=True)
        # Should not attempt to create a directory for empty path
        assert isinstance(result, Path)

    def test_interpolation__missing_var(self, env_instance: Environment):
        """Test interpolation with missing environment variable."""
        result = cls.interpolate('$NONEXISTENT_VAR_12345')
        # Missing vars stay as-is (not replaced)
        assert result == '$NONEXISTENT_VAR_12345'

    def test_interpolation__multiple_vars(self, env_instance: Environment, temp_env_var):
        """Test interpolation with multiple variables."""
        temp_env_var('VAR1', 'first')
        temp_env_var('VAR2', 'second')
        temp_env_var('VAR3', 'third')

        result = cls.interpolate('$VAR1/$VAR2/${VAR3}')
        assert result == 'first/second/third'

    def test_cache_persistence(self, env_instance: Environment, temp_env_var):
        """Test that caching works correctly."""
        temp_env_var('CACHE_VAR', 'cached_value')

        # First access
        result1 = env_instance.get('CACHE_VAR')
        # Second access (should use cache)
        result2 = env_instance.get('CACHE_VAR')

        assert result1 == result2 == 'cached_value'

    def test_special_characters_in_values(self, env_instance: Environment, temp_env_var):
        """Test environment values with special characters."""
        special_value = 'value!@#$%^&*()[]{}|\\;:\'"<>,.?/~`'
        temp_env_var('SPECIAL_VAR', special_value)

        result = env_instance.get('SPECIAL_VAR')
        assert result == special_value

    def test_unicode_in_values(self, env_instance: Environment, temp_env_var):
        """Test environment values with Unicode characters."""
        unicode_value = 'Hello 世界 🌍'
        temp_env_var('UNICODE_VAR', unicode_value)

        result = env_instance.get('UNICODE_VAR')
        assert result == unicode_value

    def test_flag__whitespace_handling(self, env_instance: Environment, temp_env_var):
        """Test that flag method strips whitespace."""
        temp_env_var('WHITESPACE_FLAG', ' 42 ')
        result = env_instance.flag('WHITESPACE_FLAG')
        assert result == 42

    def test_rgxs_class_variable(self):
        """Test that RGXS RegexStore is properly configured."""
        assert cls.RGXS is not None
        assert 'name' in cls.RGXS
        assert 'interpolation' in cls.RGXS
        assert 'truthy' in cls.RGXS
