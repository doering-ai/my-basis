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
import footprint is desired.

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
