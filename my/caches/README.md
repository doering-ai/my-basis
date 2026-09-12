# Caches

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

Start with `Cache` when a bounded in-memory map is enough. The other three classes add nested keys, sharded disk storage, or expiry. All come with [myBasis](../../README.md#installation).

</blockquote>

## Cache

<blockquote class="artificial-prose">

`Cache` is a Pydantic generic implementing a bucket-pruned LRU map. The constructor calls the size limit `maxsize` and the eviction batch `bucket_size`. Reads move an existing key to the newest end of insertion order. A new write at the limit prunes the oldest bucket before storing the value.

</blockquote>

```python
from my import Cache

cache = Cache[str, int](maxsize=4, bucket_size=2)
for i, key in enumerate('abcd'):
    cache[key] = i
_ = cache['a']
cache['e'] = 4
assert cache.keys() == ['d', 'a', 'e']
```

## NestedCache

<blockquote class="artificial-prose">

`NestedCache` takes a signature tuple such as `(str, int)` and stores a value at each matching tuple path. Nested children maintain their own access order. `set()` and `delete()` return the number of newly added or removed leaves, while `items()`, `keys()`, and `values()` walk the complete paths. When `max_size` is exceeded, pruning is distributed approximately according to child sizes.

</blockquote>

```python
from my import NestedCache

cache = NestedCache(signature=(str, int))
cache[('user', 1)] = 'robb'
assert cache.set(('user', 2), 'ada') == 1
assert cache[('user', 1)] == 'robb'
assert len(cache) == 2
assert cache.delete(('user', 2)) == 1
```

## FileCache

<blockquote class="artificial-prose">

`FileCache` keeps hot deserialized items in memory and indexes cold items under `group/prefix/file`. Its default writer and reader use JSON. The prefix is derived from the file stem, and the cache can move a shard from memory to disk or back again. `prune()` writes older items before dropping them from memory and apportions work across groups. The constructor requires an existing cache directory.

</blockquote>

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from my import FileCache

with TemporaryDirectory() as directory:
    cache = FileCache(Path(directory))
    cache.write('users', 'robb_doering', {'role': 'author'})
    assert cache[('users', 'robb_doering')] == {'role': 'author'}
```

## PickleCache

<blockquote class="artificial-prose">

`PickleCache` checks fresh in-memory data first, then a pickle file whose modification time is inside the configured TTL, and finally an optional async callback. A callback result is written back to disk, and writes use a temporary file followed by an atomic replacement. The default TTL is one day.

Pickle is a trust boundary. `read()` calls `pickle.loads()` on the cache file, so the file must be trusted local storage rather than an interchange format. Do not point this class at bytes supplied by another party.

</blockquote>
