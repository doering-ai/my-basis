# Agent Development Guidelines

The myBasis Python package, imported as `my`, provides utilities for text processing, functional programming, and runtime type coercion.
It is designed for use as a library, with a deliberately flat structure.
Its ethos is the Zen of Python (`python -c "import this"`).

## Commands

Run `task --list` for every command.
Pass `-- ARGS` to forward arguments to the underlying tool, for example `task test -- -v tests/apis/test_Environment.py::TestEnvironment::test_get`.

## Specifics

### Testing Guide

When making significant changes to tests, read and apply `tests/README.md`.

### Class Sections

Large classes use four comment-delimited subsections, in this order, each marked by a banner:

```python
# -------------------
# `0` Initial Methods
# -------------------
```

- `0` Initial Methods: initialization, pydantic validators, static constructors.
- `-` Private Methods: helpers for internal use only.
- `+` Primary Methods: the main methods, for internal or external use.
- `x` Public Methods: the primary public interface, including overloads and properties.

Python file layout and style follow `~/my/corpus/skills/100-code/references/py.md`.
Annotate everything, put `# type: ignore` on the line only when unavoidable, and write Google-style docstrings that do not repeat the annotations.

### Examples

Every non-trivial public feature carries an executed `Examples:` block in one shape.
End the lead-in with `::`, leave a blank line, then indent a doctest.
Never use markdown fences: they render broken through `eval-rst`.
`tests/test_examples.py` sweeps every module's doctests inside the ordinary suite.
A behavior change therefore needs its docstring example updated in the same commit, or the suite goes red.
Opt a side-effectful or connection-gated example out inline with `# doctest: +SKIP`.
The README's "What's inside" table enumerates `__all__`, so adding or removing an export means touching that table.

### Cast semantics

- String casts never strip.
  `cast('  test  ', str)` returns the value verbatim.
  Per-type parsers handle the whitespace they care about at parse time, so do not add `.strip()` to string-producing transforms or to `clean_data`.
- `my.typing` assumes UTC.
  Serializing a `datetime` or `time` drops the offset (`replace(tzinfo=None)`, with no conversion), so `10:20:30+00:00` becomes `10:20:30`.
  Parsing normalizes naive inputs to UTC.

### Regex performance

`RegexStore.match(name, text)` builds a pydantic `MatchData`, which costs roughly 13x a bare match on a short line (measured 0.055 s against 0.0043 s per 20,000 calls on Python 3.14).
Use it for one-off validation, via `RGXS.fullmatch(...)`.
In a per-line hot loop, call the store's compiled pattern, `RGXS['name'].match(line)`, which the store still owns.
