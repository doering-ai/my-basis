# Typing

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

`my.typing` makes runtime work with annotations explicit: parse a shape, check a value, compare two shapes, or coerce a value toward one. `Typist` gathers those operations behind the shared `ty` and `typist` facade; use the [project README](../../README.md) for installation.

</blockquote>

## Typing hierarchy

```yaml
Atom: [Scalar, String, Time, Enum]
  Scalar: [int, float, complex, bool]
  String: [str, bytes, Buff]
    Stream: [bytearray, memoryview, IO]
  Time: [date, time, datetime, timedelta]
Struct: [Vec, Map, Iterable, AsyncIterable, Model]
  Vec: [list, tuple, Set, deque]
  Map: [Mapping, ItemsView, 'list[tuple[Hashable, Any]]']
  Model: [pydantic.BaseModel, Dataclass]
  Iter: [Iterable, AsyncIterable]
Func: [FunctionType, BuiltinFunctionType, Callable]
```

## Architecture

<blockquote class="artificial-prose">

`MyType` is the normalized representation that the rest of the package uses instead of inspecting raw annotations ad hoc. A `dict[str, int]` annotation, for example, records its root, key type, and value type in the same family of fields used for unions, literals, enums, and generics.

The three chambers have distinct jobs: `tyc` checks a runtime value against a type, `tym` compares type shapes, and `tyt` coerces a value. `TypeCheck`, `TypeMatch`, and `TypeCast` provide those chambers; `Typist` combines them into the public facade.

Casting selects registered transforms from `_TRANSFORMS` by source and target `MyType` containment, then tries the most specific candidates first. A `Transform` carries one cast’s data and its source and target representations. It is a plain class because it is created in the hot cast path and does not cross a validation or serialization boundary.

</blockquote>

## Pydantic boundaries

<blockquote class="artificial-prose">

Pydantic models remain useful where data is validated, coerced, or serialized at a boundary. `MyType` and the public value objects therefore keep model behavior. `Transform` keeps direct attributes instead: repeatedly validating its nested type representations would add work to every cast and can recurse through the self-referential `POS` sentinel.

`AutocastModel` applies the same casting system to a Pydantic model’s fields during validation and simplifies nested values during serialization. It is a separate opt-in model base, not a change to Pydantic’s ordinary models.

</blockquote>

## Cast configuration

<blockquote class="artificial-prose">

`CastFlags` freezes the leniency policy at a public `cast()` entry point. The global `Typist` still provides process-wide defaults, but an in-flight cast sees one snapshot even if a later call changes those defaults. `strict`, `basic`, and `flex` presets supply complete bundles; callers can also pass an explicit `CastFlags` value.

</blockquote>

| Flag      | Conversion it permits                                                                |
| --------- | ------------------------------------------------------------------------------------ |
| `firsts`  | Collapse a multi-element series to its first value (`[1, 2] -> 1`).                  |
| `atomics` | Unwrap a single-element series (`[1] -> 1`).                                         |
| `splits`  | Split a string before casting it to a collection.                                    |
| `wraps`   | Wrap an atom into a collection, and perform the corresponding structural conversion. |

<blockquote class="artificial-prose">

`check` and `match` have no equivalent behavior flags. Their task is to report the relation they were asked to evaluate; leniency belongs to coercion, where the caller can choose it deliberately.

Dispatch candidate lists are memoized with the resolved flag state in the key; complete cast results are not memoized.
`Typist` does not read configuration from the environment.
Applications that want environment- or file-driven defaults supply them explicitly.

</blockquote>
