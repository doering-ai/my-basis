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
