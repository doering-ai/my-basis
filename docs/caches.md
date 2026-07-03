---
numbering:
  title: true
---

# `my.caches`: Extensible, Performant Local Caches

```{py:currentmodule} my.caches
```

This subpackage provides a suite of specialized caching implementations, each optimized for
different data access patterns and persistence requirements.

All cache classes are built on Pydantic for validation and use generic typing for type safety.

```{toctree}
---
maxdepth: 2
---
caches.Cache
caches.FileCache
caches.NestedCache
caches.PickleCache
```
