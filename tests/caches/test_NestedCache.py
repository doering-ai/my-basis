############
### HEAD ###
############
### STANDARD
from typing import Any

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.caches import NestedCache
from ..conftest import boolmap

############
### DATA ###
############
cls = NestedCache


############
### BODY ###
############
class TestNestedCache:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'signature, expected_depth',
        [
            ((int,), 1),
            ((int, str), 2),
            ((int, str, float), 3),
            ((str, str, str, str), 4),
        ],
    )
    def test_init(self, signature: tuple, expected_depth: int):
        cache = cls(signature=signature)
        assert cache.signature == signature
        assert cache.depth == expected_depth
        assert cache.size == 0
        assert cache.data == {}
        assert cache.children == {}

    def test_init__defaults(self):
        cache = cls(signature=(int,))
        assert cache.max_size == 2**12
        assert cache.bucket_size == 2**8

    # -------------------
    # `-` Private Methods
    # -------------------
    # (No private methods to test)

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'signature, keys, value',
        [
            ((int,), (1,), 'value1'),
            ((int, str), (1, 'a'), 'value2'),
            ((int, str, float), (1, 'a', 1.5), 'value3'),
            ((str, str), ('x', 'y'), 100),
        ],
    )
    def test_set(self, signature: tuple, keys: tuple, value: Any):
        cache = cls(signature=signature)
        count = cache.set(keys, value)
        assert count == 1
        assert cache.size == 1
        assert cache[keys] == value

    def test_set__overwrite_existing(self):
        cache = cls(signature=(int,))
        cache.set((1,), 'old')
        count = cache.set((1,), 'new')
        assert count == 0  # No new items added
        assert cache.size == 1
        assert cache[(1,)] == 'new'

    def test_set__depth_1_multiple_items(self):
        cache = cls(signature=(int,))
        cache.set((1,), 'a')
        cache.set((2,), 'b')
        cache.set((3,), 'c')

        assert cache.size == 3
        assert cache[(1,)] == 'a'
        assert cache[(2,)] == 'b'
        assert cache[(3,)] == 'c'

    def test_set__depth_2_multiple_items(self):
        cache = cls(signature=(int, str))
        cache.set((1, 'a'), 'value1')
        cache.set((1, 'b'), 'value2')
        cache.set((2, 'a'), 'value3')

        assert cache.size == 3
        assert cache[(1, 'a')] == 'value1'
        assert cache[(1, 'b')] == 'value2'
        assert cache[(2, 'a')] == 'value3'

    def test_set__raises_on_wrong_depth(self):
        cache = cls(signature=(int, str))
        with pyt.raises(ValueError, match='Keys must match the depth'):
            cache.set((1,), 'value')

        with pyt.raises(ValueError, match='Keys must match the depth'):
            cache.set((1, 'a', 'b'), 'value')

    @pyt.mark.parametrize(
        'signature, keys, value',
        [
            ((int,), (1,), 'value'),
            ((int, str), (1, 'a'), 100),
            ((int, str, float), (1, 'a', 1.5), [1, 2, 3]),
        ],
    )
    def test_delete__existing(self, signature: tuple, keys: tuple, value: Any):
        cache = cls(signature=signature)
        cache.set(keys, value)
        assert cache.size == 1

        count = cache.delete(keys)
        assert count == 1
        assert cache.size == 0
        assert cache[keys] is None

    def test_delete__nonexistent(self):
        cache = cls(signature=(int,))
        count = cache.delete((999,))
        assert count == 0
        assert cache.size == 0

    def test_delete__wrong_depth(self):
        cache = cls(signature=(int, str))
        count = cache.delete((1,))
        assert count == 0

        count = cache.delete((1, 'a', 'b'))
        assert count == 0

    def test_delete__cleans_empty_children(self):
        cache = cls(signature=(int, str))
        cache.set((1, 'a'), 'value1')
        cache.set((1, 'b'), 'value2')

        # Delete one item
        cache.delete((1, 'a'))
        assert cache.size == 1
        assert 1 in cache.children  # Child still exists

        # Delete the other item
        cache.delete((1, 'b'))
        assert cache.size == 0
        assert 1 not in cache.children  # Child should be removed

    @pyt.mark.parametrize(
        'signature, n, initial_size',
        [
            ((int,), 5, 10),
            ((int,), 10, 10),
            ((int, str), 3, 10),
            ((int, str, float), 5, 15),
        ],
    )
    def test_prune(self, signature: tuple, n: int, initial_size: int):
        cache = cls(signature=signature)

        # Populate cache
        for i in range(initial_size):
            if len(signature) == 1:
                cache[i,] = f'value_{i}'
            elif len(signature) == 2:
                cache[i % 5, str(i)] = f'value_{i}'
            elif len(signature) == 3:
                cache[i % 3, str(i), float(i)] = f'value_{i}'

        removed = cache.prune(n)
        assert cache.size <= (initial_size - n)
        assert removed > 0

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    @pyt.mark.parametrize(
        'signature, items, expected_len',
        [
            ((int,), [(1,), (2,), (3,)], 3),
            ((int, str), [(1, 'a'), (1, 'b'), (2, 'a')], 3),
            ((int, str, float), [(1, 'a', 1.0), (1, 'a', 2.0)], 2),
        ],
    )
    def test_len(self, signature: tuple, items: list[tuple], expected_len: int):
        cache = cls(signature=signature)
        for i, keys in enumerate(items):
            cache.set(keys, f'value_{i}')
        assert len(cache) == expected_len

    @pyt.mark.parametrize(
        'signature, keys, value',
        [
            ((int,), (1,), 'test'),
            ((int, str), (5, 'key'), 42),
            ((str, str, str), ('a', 'b', 'c'), [1, 2, 3]),
        ],
    )
    def test_contains(self, signature: tuple, keys: tuple, value: Any):
        cache = cls(signature=signature)
        assert keys not in cache

        cache.set(keys, value)
        assert keys in cache

        cache.delete(keys)
        assert keys not in cache

    @pyt.mark.parametrize(
        'signature, items, expected',
        boolmap(
            true=[
                ((int,), [(1,), (2,)]),
                ((int, str), [(1, 'a')]),
            ],
            false=[
                ((int,), []),
                ((int, str), []),
            ],
        ),
    )
    def test_bool(self, signature: tuple, items: list[tuple], expected: bool):
        cache = cls(signature=signature)
        for keys in items:
            cache.set(keys, 'value')
        assert bool(cache) == expected

    def test_getitem__depth_1(self):
        cache = cls(signature=(int,))
        cache.set((1,), 'value1')
        cache.set((2,), 'value2')

        assert cache[(1,)] == 'value1'
        assert cache[(2,)] == 'value2'
        assert cache[(999,)] is None

    def test_getitem__depth_2(self):
        cache = cls(signature=(int, str))
        cache.set((1, 'a'), 'value1')
        cache.set((1, 'b'), 'value2')

        assert cache[(1, 'a')] == 'value1'
        assert cache[(1, 'b')] == 'value2'
        assert cache[(999, 'x')] is None

    def test_getitem__wrong_depth_returns_none(self):
        cache = cls(signature=(int, str))
        cache.set((1, 'a'), 'value')

        assert cache[(1,)] is None
        assert cache[(1, 'a', 'extra')] is None

    def test_getitem__moves_to_end(self):
        """Test that accessing an item moves it to the end (LRU)."""
        cache = cls(signature=(int,))
        cache.set((1,), 'a')
        cache.set((2,), 'b')
        cache.set((3,), 'c')

        # Access item 1
        _ = cache[(1,)]

        # Prune 1 item - should remove 2 (oldest after access)
        cache.prune(1)

        assert (1,) in cache
        assert (2,) not in cache or (3,) not in cache

    def test_setitem__depth_1(self):
        cache = cls(signature=(int,))
        cache[(1,)] = 'value'

        assert cache[(1,)] == 'value'
        assert cache.size == 1

    def test_setitem__auto_prune_when_full(self):
        cache = cls(signature=(int,), max_size=10, bucket_size=5)

        # Fill to capacity
        for i in range(10):
            cache[(i,)] = f'value_{i}'

        assert cache.size == 10

        # Adding one more should trigger pruning
        cache[(10,)] = 'value_10'

        assert cache.size == 6  # 10 - 5 + 1
        assert (10,) in cache

    # ---------------
    # `*1` Properties
    # ---------------
    @pyt.mark.parametrize(
        'signature, expected_depth',
        [
            ((int,), 1),
            ((int, str), 2),
            ((int, str, float), 3),
            ((str, str, str, str, str), 5),
        ],
    )
    def test_depth(self, signature: tuple, expected_depth: int):
        cache = cls(signature=signature)
        assert cache.depth == expected_depth

    # ------------
    # `*2` Methods
    # ------------
    def test_items__depth_1(self):
        cache = cls(signature=(int,))
        cache.set((1,), 'a')
        cache.set((2,), 'b')

        items = list(cache.items())
        assert len(items) == 2
        assert ((1,), 'a') in items
        assert ((2,), 'b') in items

    def test_items__depth_2(self):
        cache = cls(signature=(int, str))
        cache.set((1, 'a'), 'value1')
        cache.set((1, 'b'), 'value2')
        cache.set((2, 'a'), 'value3')

        items = list(cache.items())
        assert len(items) == 3
        assert ((1, 'a'), 'value1') in items
        assert ((1, 'b'), 'value2') in items
        assert ((2, 'a'), 'value3') in items

    def test_items__depth_3(self):
        cache = cls(signature=(int, str, float))
        cache.set((1, 'a', 1.0), 'v1')
        cache.set((1, 'a', 2.0), 'v2')

        items = list(cache.items())
        assert len(items) == 2
        assert ((1, 'a', 1.0), 'v1') in items
        assert ((1, 'a', 2.0), 'v2') in items

    def test_keys(self):
        cache = cls(signature=(int, str))
        cache.set((1, 'a'), 'value1')
        cache.set((2, 'b'), 'value2')

        keys = list(cache.keys())
        assert len(keys) == 2
        assert (1, 'a') in keys
        assert (2, 'b') in keys

    def test_values(self):
        cache = cls(signature=(int, str))
        cache.set((1, 'a'), 'value1')
        cache.set((2, 'b'), 'value2')

        values = list(cache.values())
        assert len(values) == 2
        assert 'value1' in values
        assert 'value2' in values

    # ----------------
    # Edge Cases Tests
    # ----------------
    def test_empty_cache_operations(self):
        """Test operations on empty cache."""
        cache = cls(signature=(int,))

        assert len(cache) == 0
        assert not bool(cache)
        assert list(cache.items()) == []
        assert list(cache.keys()) == []
        assert list(cache.values()) == []
        assert cache.prune(10) == 0

    def test_deeply_nested_cache(self):
        """Test cache with depth 5."""
        cache = cls(signature=(int, str, float, bool, str))
        keys = (1, 'a', 1.5, True, 'x')
        cache.set(keys, 'deep_value')

        assert cache[keys] == 'deep_value'
        assert cache.size == 1

        cache.delete(keys)
        assert cache.size == 0

    def test_proportional_pruning(self):
        """Test that pruning is distributed proportionally across children."""
        cache = cls(signature=(int, str), max_size=100, bucket_size=20)

        # Add items to different top-level keys
        for i in range(30):
            cache.set((1, f'a_{i}'), f'value1_{i}')

        for i in range(10):
            cache.set((2, f'b_{i}'), f'value2_{i}')

        assert cache.size == 40

        # Prune 20 items
        removed = cache.prune(20)

        # Should have pruned proportionally
        assert removed == 20
        assert cache.size == 20

    def test_nested_children_cleanup(self):
        """Test that empty child caches are removed."""
        cache = cls(signature=(int, str, float))

        cache.set((1, 'a', 1.0), 'v1')
        cache.set((1, 'a', 2.0), 'v2')
        cache.set((1, 'b', 1.0), 'v3')

        assert 1 in cache.children
        assert 'a' in cache.children[1].children

        # Delete all items under (1, 'a')
        cache.delete((1, 'a', 1.0))
        cache.delete((1, 'a', 2.0))

        # Child 'a' should be removed
        assert 'a' not in cache.children[1].children
        assert 'b' in cache.children[1].children

        # Delete last item
        cache.delete((1, 'b', 1.0))

        # All children should be cleaned up
        assert 1 not in cache.children

    def test_mixed_type_keys(self):
        """Test cache with various hashable key types."""
        cache = cls(signature=(int, str))

        cache.set((1, 'test'), 'value1')
        cache.set((999, 'foo'), 'value2')
        cache.set((-5, 'bar'), 'value3')

        assert cache[(1, 'test')] == 'value1'
        assert cache[(999, 'foo')] == 'value2'
        assert cache[(-5, 'bar')] == 'value3'

    def test_large_nested_cache(self):
        """Test cache with many items at depth 2."""
        cache = cls(signature=(int, int), max_size=500, bucket_size=100)

        # Add 500 items
        for i in range(50):
            for j in range(10):
                cache[i, j] = f'value_{i}_{j}'

        assert cache.size == 500

        # Add more to trigger pruning
        for i in range(50, 100):
            cache[i, 0] = f'value_{i}_0'

        # Should have triggered pruning
        assert cache.size == 450

    def test_child_cache_inherits_signature(self):
        """Test that child caches have correct signature."""
        cache = cls(signature=(int, str, float))
        cache.set((1, 'a', 1.0), 'value')

        # Access child cache
        child = cache.children[1]
        assert child.signature == (str, float)
        assert child.depth == 2

    def test_child_cache_inherits_config(self):
        """Test that child caches propagate the parent's max_size/bucket_size, not defaults."""
        cache = cls(signature=(int, int), max_size=10, bucket_size=2)
        cache.set((1, 2), 'value')

        child = cache.children[1]
        assert child.max_size == 10
        assert child.bucket_size == 2
        assert child.max_size != cls.model_fields['max_size'].default
        assert child.bucket_size != cls.model_fields['bucket_size'].default
