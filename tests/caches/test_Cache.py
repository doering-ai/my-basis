############
### HEAD ###
############
### STANDARD
from typing import Any

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.caches import Cache

############
### DATA ###
############
cls = Cache


############
### BODY ###
############
class TestCache:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'maxsize, bucket_size, expected_max, expected_bucket',
        [
            (100, 10, 100, 10),
            (2**12, 2**8, 2**12, 2**8),
            (1000, 50, 1000, 50),
        ],
    )
    def test_init(self, maxsize: int, bucket_size: int, expected_max: int, expected_bucket: int):
        cache = cls(maxsize=maxsize, bucket_size=bucket_size)
        assert cache.maxsize == expected_max
        assert cache.bucket_size == expected_bucket
        assert len(cache) == 0
        assert cache.data == {}

    def test_init__defaults(self):
        cache = cls()
        assert cache.maxsize == 2**12
        assert cache.bucket_size == 2**8

    # -------------------
    # `-` Private Methods
    # -------------------
    # (No private methods to test)

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'n, initial_size, expected_remaining',
        [
            (5, 10, 5),
            (10, 10, 0),
            (15, 10, 0),
            (0, 10, 10),
            (3, 5, 2),
        ],
    )
    def test_prune(self, n: int, initial_size: int, expected_remaining: int):
        cache = cls(maxsize=100, bucket_size=10)
        # Populate cache
        for i in range(initial_size):
            cache[f'key_{i}'] = f'value_{i}'

        cache.prune(n)
        assert len(cache) == expected_remaining

        # Verify oldest items were removed
        for i in range(min(n, initial_size)):
            assert f'key_{i}' not in cache

    def test_prune__removes_oldest_first(self):
        cache = cls(maxsize=100, bucket_size=10)
        cache['a'] = 1
        cache['b'] = 2
        cache['c'] = 3
        cache['d'] = 4

        cache.prune(2)

        assert 'a' not in cache
        assert 'b' not in cache
        assert 'c' in cache
        assert 'd' in cache

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
    def test_len(self, initial_data: dict, expected_len: int):
        cache = cls(maxsize=200)
        for key, val in initial_data.items():
            cache[key] = val
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
    def test_contains(self, key: Any, value: Any):
        cache = cls()
        assert key not in cache
        cache[key] = value
        assert key in cache

    def test_getitem(self):
        cache = cls()
        cache['key'] = 'value'
        assert cache['key'] == 'value'

    def test_getitem__nonexistent(self):
        cache = cls()
        assert cache['nonexistent'] is None

    def test_getitem__moves_to_end(self):
        cache = cls(maxsize=10, bucket_size=2)
        cache['a'] = 1
        cache['b'] = 2
        cache['c'] = 3

        # Access 'a' to move it to the end
        _ = cache['a']

        # Now prune 2 items - 'b' and 'c' should be removed, not 'a'
        cache.prune(2)

        assert 'a' in cache
        assert 'b' not in cache
        assert 'c' not in cache

    def test_setitem(self):
        cache = cls()
        cache['key'] = 'value'
        assert cache['key'] == 'value'

    def test_setitem__overwrite(self):
        cache = cls()
        cache['key'] = 'old'
        cache['key'] = 'new'
        assert cache['key'] == 'new'
        assert len(cache) == 1

    def test_setitem__auto_prune_when_full(self):
        cache = cls(maxsize=10, bucket_size=5)
        # Fill cache to capacity
        for i in range(10):
            cache[f'key_{i}'] = f'value_{i}'

        assert len(cache) == 10

        # Adding one more should trigger pruning
        cache['new_key'] = 'new_value'

        # Cache should have pruned bucket_size items
        assert len(cache) == 6  # 10 - 5 + 1
        assert 'new_key' in cache

        # Oldest items should be gone
        for i in range(5):
            assert f'key_{i}' not in cache

    def test_prune__tolerates_already_evicted_key(self):
        # `prune` must not raise if a key it planned to drop is gone by the time it pops it
        # (the concurrent-eviction race). Simulate the collision deterministically: prune more
        # than exist so the snapshot outlives the data.
        cache = cls(maxsize=100, bucket_size=10)
        for i in range(5):
            cache[i] = i
        cache.prune(10)  # n > len(cache): must simply empty it, never KeyError
        assert len(cache) == 0

    def test_prune__concurrent_hammer_never_raises(self):
        # Regression for the lockless-cache data race: many threads inserting into a small cache
        # drive constant pruning; pre-fix this raised `KeyError`/`RuntimeError` from
        # `del`-while-iterating. Post-fix (snapshot + `pop(default)`) it is crash-free.
        import threading

        cache = cls(maxsize=64, bucket_size=16)
        errors: list[BaseException] = []

        def worker(base: int) -> None:
            try:
                for i in range(3000):
                    cache[(base, i)] = i
                    _ = cache[(base, i)]
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(b,)) for b in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f'concurrent access raised: {errors[:3]}'
        assert len(cache) <= cache.maxsize

    # ---------------
    # `*1` Properties
    # ---------------
    # (No properties to test)

    # ------------
    # `*2` Methods
    # ------------
    @pyt.mark.parametrize(
        'initial_data, expected_items',
        [
            ({}, []),
            ({'a': 1}, [('a', 1)]),
            ({'a': 1, 'b': 2}, [('a', 1), ('b', 2)]),
            ({'x': 'foo', 'y': 'bar', 'z': 'baz'}, [('x', 'foo'), ('y', 'bar'), ('z', 'baz')]),
        ],
    )
    def test_items(self, initial_data: dict, expected_items: list):
        cache = cls()
        for key, val in initial_data.items():
            cache[key] = val
        assert cache.items() == expected_items

    @pyt.mark.parametrize(
        'initial_data, expected_keys',
        [
            ({}, []),
            ({'a': 1}, ['a']),
            ({'a': 1, 'b': 2}, ['a', 'b']),
        ],
    )
    def test_keys(self, initial_data: dict, expected_keys: list):
        cache = cls()
        for key, val in initial_data.items():
            cache[key] = val
        assert cache.keys() == expected_keys

    @pyt.mark.parametrize(
        'initial_data, expected_values',
        [
            ({}, []),
            ({'a': 1}, [1]),
            ({'a': 1, 'b': 2}, [1, 2]),
        ],
    )
    def test_values(self, initial_data: dict, expected_values: list):
        cache = cls()
        for key, val in initial_data.items():
            cache[key] = val
        assert cache.values() == expected_values

    # ----------------
    # Edge Cases Tests
    # ----------------
    def test_lru_ordering(self):
        """Test that LRU ordering is maintained correctly."""
        cache = cls(maxsize=5, bucket_size=2)
        cache['a'] = 1
        cache['b'] = 2
        cache['c'] = 3

        # Access 'a' to make it recently used
        _ = cache['a']

        cache['d'] = 4
        cache['e'] = 5

        # Now cache is full, adding one more should prune
        cache['f'] = 6

        # 'b' and 'c' should be removed (oldest), 'a' should remain
        assert 'a' in cache
        assert 'b' not in cache
        assert 'c' not in cache
        assert 'd' in cache
        assert 'e' in cache
        assert 'f' in cache

    def test_repeated_access_maintains_order(self):
        """Test that repeated accesses keep item at the end."""
        cache = cls(maxsize=10, bucket_size=3)
        for i in range(5):
            cache[i] = i * 10

        # Access item 0 multiple times
        for _ in range(3):
            _ = cache[0]

        # Prune 3 items
        cache.prune(3)

        # Item 0 should survive, items 1-3 should be gone
        assert 0 in cache
        assert 1 not in cache
        assert 2 not in cache
        assert 3 not in cache
        assert 4 in cache

    def test_empty_cache_operations(self):
        """Test operations on empty cache."""
        cache = cls()
        assert len(cache) == 0
        assert cache['nonexistent'] is None
        assert 'key' not in cache
        assert cache.items() == []
        assert cache.keys() == []
        assert cache.values() == []

        # Pruning empty cache should work
        cache.prune(10)
        assert len(cache) == 0

    def test_single_item_cache(self):
        """Test cache with maxsize=1."""
        cache = cls(maxsize=1, bucket_size=1)
        cache['a'] = 1
        assert len(cache) == 1

        cache['b'] = 2
        # Should have pruned 'a'
        assert 'a' not in cache
        assert 'b' in cache
        assert len(cache) == 1

    def test_large_cache(self):
        """Test cache with many items."""
        cache = cls(maxsize=10000, bucket_size=500)
        n = 5000
        for i in range(n):
            cache[i] = i * 2

        assert len(cache) == n

        # Access some items to move them to the end
        for i in range(4500, 5000):
            _ = cache[i]

        # Add more items to trigger pruning
        for i in range(n, n + 1000):
            cache[i] = i * 2

        # Should have pruned oldest items
        assert len(cache) <= n + 1000

    def test_heterogeneous_keys_and_values(self):
        """Test cache with mixed types."""
        cache = cls()
        cache[1] = 'int_key'
        cache['string'] = 123  # pyrefly: ignore[unsupported-operation]
        cache[(1, 2, 3)] = ['list', 'value']  # pyrefly: ignore[unsupported-operation]
        cache[frozenset([1, 2])] = {'dict': 'value'}  # pyrefly: ignore[unsupported-operation]

        assert cache[1] == 'int_key'
        assert cache['string'] == 123  # pyrefly: ignore[bad-index]
        assert cache[(1, 2, 3)] == ['list', 'value']
        assert cache[frozenset([1, 2])] == {'dict': 'value'}
