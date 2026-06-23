############
### HEAD ###
############
### STANDARD
from datetime import timedelta
from pathlib import Path
from typing import Any
import pickle as pkl

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.caches import PickleCache
from my.utils import ut

############
### DATA ###
############
cls = PickleCache


############
### BODY ###
############
class TestPickleCache:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.fixture
    def temp_cache_file(self, tmp_path: Path) -> Path:
        """Create a temporary file path for cache testing."""
        return tmp_path / 'test_cache.pkl'

    @pyt.fixture
    def cache(self, temp_cache_file: Path) -> PickleCache:
        """Create a basic PickleCache instance."""
        return cls(file=temp_cache_file)

    def test_init(self, temp_cache_file: Path):
        cache = cls(file=temp_cache_file)
        assert cache.file == temp_cache_file.resolve()
        assert cache.data == {}
        assert cache.func is None
        assert cache.ttl == timedelta(days=1)

    def test_init__with_data(self, temp_cache_file: Path):
        data = {'key1': 'value1', 'key2': 'value2'}
        cache = cls(file=temp_cache_file, data=data)

        assert cache.data == data
        assert cache.file.exists()

        # Verify data was written to file
        with cache.file.open('rb') as f:
            loaded = pkl.load(f)
        assert loaded == data

    def test_init__custom_ttl(self, temp_cache_file: Path):
        cache = cls(file=temp_cache_file, ttl=timedelta(hours=6))
        assert cache.ttl == timedelta(hours=6)

    def test_init__creates_parent_directory(self, tmp_path: Path):
        nested_path = tmp_path / 'nested' / 'dir' / 'cache.pkl'
        cache = cls(file=nested_path)

        assert cache.file.parent.exists()
        assert cache.file.parent.is_dir()

    def test_init__expands_user_path(self):
        cache = cls(file=Path('~/test_cache.pkl'))
        assert '~' not in str(cache.file)
        assert cache.file.is_absolute()

    # -------------------
    # `-` Private Methods
    # -------------------
    def test_build_validator(self, temp_cache_file: Path):
        """Test that _build validator is called during initialization."""
        data = {'test': 'data'}
        cache = cls(file=temp_cache_file, data=data)

        # File should exist and contain data
        assert cache.file.exists()
        with cache.file.open('rb') as f:
            assert pkl.load(f) == data

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.asyncio
    async def test_read__from_memory(self, cache: PickleCache):
        """Test reading from in-memory cache when fresh."""
        cache.data = {'key': 'value'}
        cache.last_read = ut.posix()
        cache.last_write = ut.posix() - timedelta(hours=1)

        result = await cache.read()
        assert result == {'key': 'value'}

    @pyt.mark.asyncio
    async def test_read__from_file(self, temp_cache_file: Path):
        """Test reading from filesystem when file is fresh."""
        # Write data to file
        data = {'key1': 'value1', 'key2': 'value2'}
        with temp_cache_file.open('wb') as f:
            pkl.dump(data, f)

        cache = cls(file=temp_cache_file)
        result = await cache.read()

        assert result == data
        assert cache.data == data

    @pyt.mark.asyncio
    async def test_read__from_callback(self, temp_cache_file: Path):
        """Test fetching from callback when file is stale."""

        async def fetch_data():
            return {'fresh': 'data', 'from': 'callback'}

        # Create old file
        old_data = {'old': 'data'}
        with temp_cache_file.open('wb') as f:
            pkl.dump(old_data, f)

        # Set file modification time to past TTL
        old_time = (ut.posix() - timedelta(days=2)).timestamp()
        import os

        os.utime(temp_cache_file, (old_time, old_time))

        cache = cls(file=temp_cache_file, func=fetch_data, ttl=timedelta(days=1))
        result = await cache.read()

        assert result == {'fresh': 'data', 'from': 'callback'}
        assert cache.data == result

        # Verify data was written to file
        with temp_cache_file.open('rb') as f:
            assert pkl.load(f) == result

    @pyt.mark.asyncio
    async def test_read__no_file_no_callback(self, temp_cache_file: Path):
        """Test reading when no file exists and no callback provided."""
        cache = cls(file=temp_cache_file)
        result = await cache.read()

        assert result == {}
        assert cache.data == {}

    @pyt.mark.asyncio
    async def test_read__stale_file_no_callback(self, temp_cache_file: Path):
        """Test reading stale file when no callback provided."""
        # Create old file
        old_data = {'old': 'data'}
        with temp_cache_file.open('wb') as f:
            pkl.dump(old_data, f)

        # Set file modification time to past TTL
        import os

        old_time = (ut.posix() - timedelta(days=2)).timestamp()
        os.utime(temp_cache_file, (old_time, old_time))

        cache = cls(file=temp_cache_file, ttl=timedelta(days=1))
        result = await cache.read()

        # Should return empty dict since file is stale and no callback
        assert result == {}

    def test_write(self, cache: PickleCache):
        """Test writing data to file."""
        cache.data = {'key1': 'value1', 'key2': 'value2'}
        cache.write()

        assert cache.file.exists()

        # Verify data was written correctly
        with cache.file.open('rb') as f:
            loaded = pkl.load(f)
        assert loaded == cache.data

    def test_write__updates_timestamps(self, cache: PickleCache):
        """Test that write updates both read and write timestamps."""
        before = ut.posix()
        cache.data = {'test': 'data'}
        cache.write()
        after = ut.posix()

        assert before <= cache.last_read <= after
        assert before <= cache.last_write <= after
        assert cache.last_read == cache.last_write

    def test_write__overwrites_existing(self, cache: PickleCache):
        """Test that write overwrites existing file."""
        cache.data = {'old': 'data'}
        cache.write()

        cache.data = {'new': 'data'}
        cache.write()

        with cache.file.open('rb') as f:
            loaded = pkl.load(f)
        assert loaded == {'new': 'data'}

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    @pyt.mark.parametrize(
        'initial_data, expected_len',
        [
            ({}, 0),
            ({'a': 1}, 1),
            ({'a': 1, 'b': 2, 'c': 3}, 3),
            ({i: i * 2 for i in range(100)}, 100),
        ],
    )
    def test_len(self, temp_cache_file: Path, initial_data: dict, expected_len: int):
        cache = cls(file=temp_cache_file, data=initial_data)
        assert len(cache) == expected_len

    @pyt.mark.parametrize(
        'key, value',
        [
            ('test', 'value'),
            (1, 'number_key'),
            ('key', 42),
            ((1, 2), 'tuple_key'),
        ],
    )
    def test_contains(self, cache: PickleCache, key: Any, value: Any):
        assert key not in cache
        cache[key] = value
        assert key in cache

    def test_getitem(self, cache: PickleCache):
        cache.data['key'] = 'value'
        assert cache['key'] == 'value'

    def test_getitem__raises_on_missing(self, cache: PickleCache):
        with pyt.raises(KeyError):
            _ = cache['nonexistent']

    def test_setitem(self, cache: PickleCache):
        cache['key'] = 'value'
        assert cache.data['key'] == 'value'
        assert cache['key'] == 'value'

    def test_setitem__overwrite(self, cache: PickleCache):
        cache['key'] = 'old'
        cache['key'] = 'new'
        assert cache['key'] == 'new'
        assert len(cache) == 1

    def test_delitem__existing(self, cache: PickleCache):
        cache['key'] = 'value'
        assert 'key' in cache

        del cache['key']
        assert 'key' not in cache

    def test_delitem__nonexistent(self, cache: PickleCache):
        # Should not raise, just silently succeed
        del cache['nonexistent']

    def test_ior__merge_dict(self, cache: PickleCache):
        cache.data = {'a': 1, 'b': 2}
        other = {'c': 3, 'd': 4}

        cache |= other

        assert cache.data == {'a': 1, 'b': 2, 'c': 3, 'd': 4}

    def test_ior__overwrites_existing(self, cache: PickleCache):
        cache.data = {'a': 1, 'b': 2}
        other = {'b': 999, 'c': 3}

        cache |= other

        assert cache['b'] == 999
        assert cache['c'] == 3

    # ---------------
    # `*1` Properties
    # ---------------
    # (No properties beyond Pydantic fields)

    # ------------
    # `*2` Methods
    # ------------
    @pyt.mark.parametrize(
        'key, default, expected',
        [
            ('existing', None, 'value'),
            ('nonexistent', None, None),
            ('nonexistent', 'default_value', 'default_value'),
            ('missing', 42, 42),
        ],
    )
    def test_get(self, cache: PickleCache, key: str, default: Any, expected: Any):
        cache.data = {'existing': 'value'}
        assert cache.get(key, default) == expected

    def test_items(self, cache: PickleCache):
        cache.data = {'a': 1, 'b': 2, 'c': 3}
        items = list(cache.items())

        assert ('a', 1) in items
        assert ('b', 2) in items
        assert ('c', 3) in items
        assert len(items) == 3

    def test_keys(self, cache: PickleCache):
        cache.data = {'a': 1, 'b': 2, 'c': 3}
        keys = list(cache.keys())

        assert 'a' in keys
        assert 'b' in keys
        assert 'c' in keys
        assert len(keys) == 3

    def test_values(self, cache: PickleCache):
        cache.data = {'a': 1, 'b': 2, 'c': 3}
        values = list(cache.values())

        assert 1 in values
        assert 2 in values
        assert 3 in values
        assert len(values) == 3

    # ----------------
    # Edge Cases Tests
    # ----------------
    @pyt.mark.asyncio
    async def test_ttl_expiration(self, temp_cache_file: Path):
        """Test that TTL properly expires cached data."""

        async def fetch_new():
            return {'new': 'data'}

        # Create cache with short TTL
        cache = cls(file=temp_cache_file, func=fetch_new, ttl=timedelta(seconds=1))
        cache.data = {'old': 'data'}
        cache.last_write = ut.posix() - timedelta(seconds=2)  # Expired

        result = await cache.read()
        assert result == {'new': 'data'}

    @pyt.mark.asyncio
    async def test_fresh_memory_cache(self, temp_cache_file: Path):
        """Test that fresh in-memory cache is used without file access."""
        cache = cls(file=temp_cache_file)
        cache.data = {'memory': 'data'}
        cache.last_write = cache.last_read = ut.posix()

        # Even if file exists with different data, memory should be used
        with temp_cache_file.open('wb') as f:
            pkl.dump({'file': 'data'}, f)

        result = await cache.read()
        assert result == {'memory': 'data'}

    def test_complex_data_types(self, cache: PickleCache):
        """Test caching complex Python objects."""
        complex_data = {
            'list': [1, 2, 3],
            'dict': {'nested': 'value'},
            'tuple': (1, 2, 3),
            'set': {1, 2, 3},
        }

        cache.data = complex_data
        cache.write()

        with cache.file.open('rb') as f:
            loaded = pkl.load(f)

        assert loaded['list'] == [1, 2, 3]
        assert loaded['dict'] == {'nested': 'value'}
        assert loaded['tuple'] == (1, 2, 3)
        assert loaded['set'] == {1, 2, 3}

    def test_empty_cache_operations(self, cache: PickleCache):
        """Test operations on empty cache."""
        assert len(cache) == 0
        assert 'key' not in cache
        assert list(cache.items()) == []
        assert list(cache.keys()) == []
        assert list(cache.values()) == []
        assert cache.get('key', 'default') == 'default'

    @pyt.mark.asyncio
    async def test_callback_error_handling(self, temp_cache_file: Path):
        """Test behavior when callback raises an error."""

        async def failing_callback():
            raise ValueError('Callback failed')

        cache = cls(file=temp_cache_file, func=failing_callback)

        with pyt.raises(ValueError, match='Callback failed'):
            await cache.read()

    def test_pickle_serialization_error(self, cache: PickleCache):
        """Test handling of unpicklable objects."""

        # Lambda functions can't be pickled
        class UnpicklableClass:
            def __init__(self):
                self.func = lambda x: x

        cache.data = {'unpicklable': UnpicklableClass()}

        with pyt.raises((pkl.PicklingError, AttributeError)):
            cache.write()

    @pyt.mark.asyncio
    async def test_multiple_reads_use_cache(self, temp_cache_file: Path):
        """Test that multiple reads reuse cached data."""
        call_count = 0

        async def fetch_data():
            nonlocal call_count
            call_count += 1
            return {'data': f'call_{call_count}'}

        cache = cls(file=temp_cache_file, func=fetch_data)

        # First read should call function
        result1 = await cache.read()
        assert call_count == 1
        assert result1 == {'data': 'call_1'}

        # Second read should use cached data
        result2 = await cache.read()
        assert call_count == 1  # Not called again
        assert result2 == {'data': 'call_1'}

    @pyt.mark.asyncio
    async def test_file_persistence_across_instances(self, temp_cache_file: Path):
        """Test that data persists across cache instances."""
        # First instance writes data
        cls(file=temp_cache_file, data={'key': 'value'})

        # Second instance should load from file
        cache2 = cls(file=temp_cache_file)
        result = await cache2.read()

        assert result == {'key': 'value'}

    def test_heterogeneous_keys_and_values(self, cache: PickleCache):
        """Test cache with mixed types."""
        cache[1] = 'int_key'
        cache['string'] = 123
        cache[(1, 2, 3)] = ['list', 'value']

        assert cache[1] == 'int_key'
        assert cache['string'] == 123
        assert cache[(1, 2, 3)] == ['list', 'value']

    def test_large_cache(self, cache: PickleCache):
        """Test cache with many items."""
        n = 10000
        cache.data = {i: i * 2 for i in range(n)}

        assert len(cache) == n
        assert cache[5000] == 10000

        cache.write()

        # Verify file was written
        with cache.file.open('rb') as f:
            loaded = pkl.load(f)
        assert len(loaded) == n
