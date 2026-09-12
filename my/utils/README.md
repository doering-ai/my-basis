# My Utilities

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

`my.utils` collects small typed operations behind the `Utils` facade, exported as both `ut` and `utils`. The facade is a class rather than this package module, so `from my import utils as ut` exposes the combined methods. For installation, start at the [project README](../../README.md).

</blockquote>

## Five eager utility families

<blockquote class="artificial-prose">

Five families load as the ordinary utility surface. Their public methods remain available through `ut`, while importing a concrete class is useful when a caller wants a narrower dependency or a more legible type reference.

</blockquote>

| Family          | Examples                                                                                                              |
| --------------- | --------------------------------------------------------------------------------------------------------------------- |
| `IterUtils`     | `partition`, `multi_partition`, `bucket`, `find`, `map_items`, and `val_map` for iterable and mapping work.           |
| `TextUtils`     | `replace`, `split_into`, `multi_rgx`, `regex_dict`, `indent`, and paragraph wrapping helpers.                         |
| `SystemUtils`   | POSIX-time conversion, path validation and substitution, terminal formatting, confirmation, and async bridge helpers. |
| `SyntaxUtils`   | Python-syntax and code-structure helpers, including Pydantic schema adaptation and cached-property invalidation.      |
| `SemanticUtils` | Content-level conversions such as Roman numerals, numeric formatting, singular forms, ordinals, and identifiers.      |

## Lazy metrics: the sixth family

<blockquote class="artificial-prose">

`MetricUtils` is the sixth public base of `Utils`, but its implementation loads only when a metrics method is used or its implementation module is imported. The optional `metrics` extra supplies its Pandas, Logfire, and OpenTelemetry stack. This split keeps ordinary `my` imports from warming that optional stack while preserving the same `ut` facade for metrics when it is available.

</blockquote>

## Importing the facade

<blockquote class="artificial-prose">

The top-level `my.utils` attribute intentionally names the `Utils` class, which shadows the package module at that attribute path. Use the re-exported concrete names such as `my.iter_utils` or `my.SystemUtils`, or import a class from its concrete module, when you need one family rather than the aggregate facade.

</blockquote>
