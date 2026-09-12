# Tests

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

The `my-basis` test suite uses pytest to make public behavior, edge cases, and failure boundaries explicit. Test files mirror their source trees, use `pytest as pyt`, and stay runnable from the repository. See the [development setup](../README.md#documentation-and-development) for dependencies.

</blockquote>

## Module schema

<blockquote class="artificial-prose">

Use `HEAD`, `DATA`, and `BODY` banners. The head separates standard, external, and internal imports; module data holds only genuinely shared tables or helpers. When a file tests one class, bind it as `cls` and name its test class `Test<ClassName>`.

This compact slice from `tests/types/test_Span.py` demonstrates a comment-grouped table, a sentinel for different error-call shapes, and `boolmap` for Boolean expectations.

</blockquote>

```python
############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.types import Span
from ..conftest import boolmap

cls = Span


############
### DATA ###
############


############
### BODY ###
############
class TestSpan:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'args, expected',
        [
            # Tuple inputs
            ([(1, 3)], (1, 3)),
            ([(0, 10)], (0, 10)),
            # String inputs with delimiters
            (['1-3'], (1, 3)),
            (['0/10'], (0, 10)),
        ],
    )
    def test_new(self, args: list, expected: tuple[int, int]):
        assert cls(*args) == expected

    @pyt.mark.parametrize(
        'arg0, arg1',
        [
            # Invalid tuple length
            ((1, 2, 3), -1),
            # Invalid span order
            ((5, 3), -1),
            (5, 3),
        ],
    )
    def test_constructor_invalid(self, arg0: tuple | int, arg1: int):
        with pyt.raises((AssertionError, ValueError)):  # noqa: PT012
            if arg1 == -1:
                cls(arg0)
            else:
                cls(arg0, arg1)

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    @pyt.mark.parametrize(
        'span, expected',
        boolmap(
            true=[cls(1, 5), cls(0, 10)],
            false=[cls(0, 0), cls(5, 5)],
            base_type=cls,
        ),
    )
    def test_bool(self, span: Span, expected: bool):
        assert bool(span) == expected
```

## Test-class sections and names

<blockquote class="artificial-prose">

For instance-shaped classes, lifecycle sections mirror the source class: `.` is initial methods (fixtures, constructors, validators); `-` is private methods; `+` is primary methods; and `*` is public methods. The numbered public subsections have meaningful labels rather than a progression: `*0` is commonly overrides and dunder methods, `*1` properties and cached properties, and `*2` ordinary methods. Later numbered subsections remain available for a file's real source structure.

Keep an empty lifecycle section when it communicates scope—for example, private methods tested through public behavior. Utility-shaped static collections may instead use numbered all-caps domain sections. Test methods are `test_<method>` or `test_<method>__<short_scenario>`; use at most one double-underscore separator. Docstrings are optional: retain useful existing ones, but let a clear name and table carry routine cases.

</blockquote>

## Parametrization, Boolean tables, and errors

<blockquote class="artificial-prose">

Use one comma-joined quoted argument-name string and a trailing-comma tuple per case. Group mixed rows with comments such as `# Invalid span order` or `# Adjacent, no overlap`; a boundary normally belongs in its method's table rather than in a new micro-test. Use `boolmap` from `tests/conftest.py` for predicates, always supplying both `true=` and `false=`. Set `base_type=` only if the values themselves are tuple-like or another value needs to remain atomic.

For failures, keep the error cases with the behavior and assert the union of expected exceptions. A sentinel row can select between legitimate call shapes, as `test_constructor_invalid` does above. This makes the supported and rejected boundary visible in one place.

</blockquote>

## Fixtures, isolation, and caches

<blockquote class="artificial-prose">

Fixtures are function-scoped by default; prefer `tmp_path` to hand-made temporary locations. A fixture used by one test subtree belongs in that class or subtree. Tests that mutate shared state must restore it, and tests that exercise cached lookup behavior must clear the relevant caches. `tests/apis/test_Environment.py` uses this autouse pattern because its class-level environment mapping and lookup caches are shared across tests.

</blockquote>

```python
@pyt.fixture(autouse=True)
def _isolate_environ(self) -> abc.Iterator[None]:
    snapshot = dict(cls._ENVIRON)
    yield
    cls._ENVIRON.clear()
    cls._ENVIRON.update(snapshot)
    cls._get.cache_clear()
    cls._path.cache_clear()
    cls._flag.cache_clear()
```

<blockquote class="artificial-prose">

`temp_env_var` in that same test module applies a mutation through the shared `patch` fixture and clears the same caches before each lookup. Use the smallest fixture that makes the isolation boundary explicit.

</blockquote>

## Async tests

<blockquote class="artificial-prose">

Mark an asynchronous test with `pyt.mark.asyncio` and await the result. This `MetricUtils` test checks that its instrumentation wrapper preserves an async result while recording the measurement.

</blockquote>

```python
@pyt.mark.asyncio
async def test_instrument__async(self):
    counter: dict[str, float] = {'async_test': 0}

    async def async_test():
        return 42

    instrumented = cls._instrument(async_test, counter)
    assert await instrumented() == 42
    assert counter['async_test'] >= 0
```

## Run tests

<blockquote class="artificial-prose">

Run the complete suite for the usual repository check. Pass pytest selectors after `--` for a focused file; the Task targets retain the normal coverage, debugger, and stop-on-first-failure workflows.

</blockquote>

```console
task test
task test -- -v tests/apis/test_Environment.py
task test:cov
task test:pdb
task test:dev
```

## Review checklist

<blockquote class="artificial-prose">

Before adding a test, state the public behavior and boundary it protects. Keep data deterministic, use fixtures to isolate effects, place related edge cases in one table, and avoid testing incidental private structure unless the public route cannot establish the contract. During a tests-only pass, keep source frozen and record an exposed source defect as a strict expected failure against the appropriate task; don't silently weaken the test.

</blockquote>
