# Typing

### Typing hierarchy

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

### Architecture

Strip away the line count and the subsystem is four ideas:

- **`MyType`** (`MyType.py`) — a normalized intermediate representation of any type
  annotation. `dict[str, int]` parses into `root=dict`, `keys=str`, `vals=int`; unions,
  literals, enums, and generics all collapse into the same `root`/`main`/`keys`/`vals`/`args`
  shape. Every other layer operates on this IR, never on raw annotations. It is the
  load-bearing abstraction — lean on it; anything that reaches around it and inspects a raw
  annotation is a future bug.
- **Three chambers** — `check` (does this *value* inhabit this type?), `match` (is type A a
  subset of type B?), and `cast` (coerce a value into a type), exposed as `tyc`/`tym`/`tyt`.
  Each is a mixin; `Typist` multiply-inherits all three into one facade (`typist`).
- **The transform registry** (`cast.py`) — `_TRANSFORMS` is a list of
  `(source_MyType, target_MyType, fn)` entries populated by the `@register` decorator. A cast
  filters candidates by type-containment, sorts most-specific-first, and tries each until one
  returns non-`None`. It is `functools.singledispatch` generalized to *pairs* of types with
  subtype awareness — open for extension without touching the dispatcher.
- **`Transform`** (`cast.py`) — an ephemeral object holding `(data, t0, t1)` that the
  registered functions act on. One is built per `cast()` call.

### Design principle: pydantic at boundaries, plain classes on hot paths

Almost everything in this package is a `pydantic.BaseModel`, and that is usually correct —
pydantic earns its keep wherever data is **validated, coerced, or serialized at a boundary**
(`MyType`, `Command`, `Idx`, `Buffer`, `Markdown`, the caches, and the like all use
validators/serializers and stay models).

The exception is **hot-path compute objects that hold no boundary data**. `Transform` is the
canonical case: it is constructed on *every* `cast()` call, never crosses a serialization
boundary, and wants none of pydantic's per-construction validation. It was in fact *fighting*
that machinery — its fields were typed as plain `MyType` (not `MyType[T]`) purely to dodge the
deep re-validation that recurses forever through the self-referential `POS` sentinel. So it is
a **plain class**: fields assigned directly in `__init__`, with a `ty` property mirroring
`_TypingBase.ty` for facade access.

The rule of thumb, then: **`BaseModel` for data at a boundary; a plain class (or
`pydantic.dataclasses.dataclass` when you want validation without the model machinery) for
objects that exist only to carry state through a hot loop.** Note the same principle keeps the
*singleton* chambers as models — they are constructed once at import, so validation is a
startup cost, not a per-operation one.

### Configuring casts

Coercion is the only chamber with behavioral knobs today (`check` and `match` have none).
The flags live on the `Typist` instance and gate the "loose" conversions:

- `firsts` — a multi-element series collapses to its first element (`[1, 2] -> 1`).
- `atomics` — a single-element series unwraps (`[1] -> 1`).
- `splits` — a string splits before becoming a collection (`'a.b' -> {'a', 'b'}`).
- `wraps` — an atom wraps into a collection (`'a' -> ['a']`).

Because `cast()` reads these live (results are **not** memoized), they can be toggled at
runtime — `typist.splits = False` takes effect on the next call. The corollary is a standing
constraint: **if a cast-result cache is ever added, the flag state must be part of its key**,
or a toggle will silently return a stale coercion. For preset bundles rather than individual
flags, reach for the strict/basic/flex presets instead of flipping booleans by hand.

One thing this subsystem deliberately does *not* do is read its configuration from the
environment. `Typist` stays deterministic; if an application wants env- or file-driven
defaults, it should own that itself (e.g. via `pydantic-settings`) and hand a configured
preset *in* — coercion semantics that change with an ambient env var are a reproducibility
hazard, not a feature.
