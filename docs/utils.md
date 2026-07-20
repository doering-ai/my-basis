---
numbering:
  title: true
---

# `my.utils`: Pure, Typed Functional Utilities

```{py:currentmodule} my.utils
```

The `utils` subpackage provides a comprehensive collection of utility functions organized into
specialized classes that are combined into a unified `Utils` interface and exported under the alias
`ut`. This design allows methods to be called as `ut.method()` regardless of which utility class
defines them, providing a clean, flat namespace for common operations.

Individual utility classes can still be imported for more specific use cases or when a smaller
import footprint is desired (e.g. `from my.utils.IterUtils import IterUtils`).

Note -- `utils` is the *class*, on purpose:
    Both `utils` and `ut` are bound to the `Utils` **class** itself (`utils = ut = Utils`), not to
    this submodule. That is deliberate: `from my import utils as ut` hands consumers the aggregating
    facade, so `ut.clean_string(...)`, `ut.validate_dir(...)`, etc. resolve across every base
    class through one flat namespace.

    The consequence is that the `my.utils` attribute *is* the `Utils` class, which **shadows** this
    submodule: `my.utils.iter_utils` does not resolve (the class has no such attribute) and
    `hasattr(my.utils, 'iter_utils')` is `False`. This is a design choice, not a bug -- do **not**
    "fix" it by dropping `utils` from the top-level facade; downstream code (e.g. `means`, via
    `from my import utils as ut`) depends on `utils` naming the class. See the guard test in
    `tests/utils/test_utils_facade.py`.

    To reach a specific singleton or class instead, use the names the top-level facade re-exports
    (`my.iter_utils`, `my.system_utils`, `my.SystemUtils`, ...) or import from the concrete module
    (`from my.utils.SystemUtils import SystemUtils`).

```{toctree}
---
maxdepth: 2
---
utils.IterUtils
utils.TextUtils
utils.SystemUtils
utils.SyntaxUtils
utils.SemanticUtils
utils.MetricUtils
```
