# Caches

## Cache

The `Cache` class implements a simple LRU (Least Recently Used) cache with automatic eviction. When the cache reaches its `maxsize`, it prunes entries in buckets from the front, removing the oldest items first. Items are moved to the end of the dictionary on access to maintain proper LRU ordering. The cache supports configurable bucket sizing for efficient bulk pruning operations.

## PickleCache

`PickleCache` provides persistent caching with a three-tier fallback hierarchy: in-memory data, pickle files on disk, and an optional async callback function. Data freshness is determined by a configurable TTL (time-to-live), defaulting to one day. When accessing data, the cache first checks if in-memory data is fresh, then loads from the pickle file if it exists and is within the TTL window, and finally invokes the async callback to refresh stale data. The class automatically writes refreshed data to disk and manages timestamps for efficient TTL checking.

## FileCache

The `FileCache` class implements a sophisticated two-level caching system that combines in-memory LRU with on-disk file storage. Items are organized into a hierarchical directory structure using `group/prefix/filename`, where the prefix is automatically derived from the filename. The cache maintains separate indices for hot (in-memory) and cold (on-disk) data, with automatic promotion when cold items are accessed. When memory limits are exceeded, items are proportionally pruned from each group and written to disk. The cache supports regex-based searching across both memory and disk, making it suitable for large-scale data with pattern-based access.

## NestedCache

`NestedCache` provides multi-level hierarchical caching with arbitrary nesting depth determined by a signature tuple. Each level in the hierarchy maintains its own LRU ordering, and child caches are themselves `NestedCache` instances. When pruning is needed, the removal load is distributed proportionally across child caches based on their relative sizes. The cache supports path-based access using tuples of keys, making it ideal for multi-dimensional indexing scenarios where data is naturally hierarchical.
