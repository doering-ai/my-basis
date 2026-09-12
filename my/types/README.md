# Useful Types

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

`my.types` gives recurring values a small public contract: a named representation, validation where it belongs, and operations that stay close to the value. These exports are available from the root `my` namespace; use the [project README](../../README.md) for installation.

</blockquote>

## Public exports

| Type               | Role                                                                                         |
| ------------------ | -------------------------------------------------------------------------------------------- |
| `Buffer`           | Mutable text container with regex replacement, fenced regions, and paired-delimiter helpers. |
| `Command`          | Pydantic command builder with assembly and synchronous or asynchronous execution support.    |
| `MyEnum`           | Enum base with parsing, serialization, comparison, and flag-aware operations.                |
| `Platform`         | `IntFlag` describing the local platform.                                                     |
| `Predicate`        | Pydantic predicate structure with mapping operations and YAML conversion.                    |
| `Span`             | Typed two-value range with parsing, intersection, joining, and serialization helpers.        |
| `UniqueId` / `Uid` | Validated string identifier and its public alias.                                            |

<blockquote class="artificial-prose">

Most of these types use Pydantic because they validate or serialize data at an API boundary. `Span` remains a tuple subclass for a compact range value, while `Buffer` keeps mutable text and its derived fence spans together. The table is the stable public surface; module-level behavior belongs in the API documentation and source docstrings.

</blockquote>
