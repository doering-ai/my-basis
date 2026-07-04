# Changelog

All notable changes to `my-basis` are documented here. The project has no prior tagged
release -- `0.2.0` is the first tag, closing out a multi-month typing/subpackage overhaul that
landed while the version stayed pinned at `0.1.0`. Where a change is a behavior break rather
than an internal fix, it's called out explicitly; mechanism and rationale live in the cited
commit bodies, not repeated here.

## [0.2.0] - 2026-07-02

### Subpackage & module renames

`my.text` split three ways: regex symbols (`RegexStore`, `RegexParser`, etc.) moved to
`my.regex`; `Buffer`/`Span` moved to `my.types`; `Markdown` moved to `my.files`. `my.type` was
renamed wholesale to `my.typing`. Both old import paths still work via deprecation shims
(`my/text/__init__.py`, `my/type/__init__.py`) that re-export the current surface and raise a
`DeprecationWarning` on import -- migrate off them before they're removed. Not every old
symbol has a shim: `my.text`'s `atom`/`debug_regex` free functions and `my.type`'s `TimeType`
alias had no unambiguous modern equivalent and were dropped outright; see the shim docstrings
for the full accounting.

Within `my.typing`, three files were also renamed to a shorter, chamber-oriented convention:
`typecast.py` -> `cast.py`, `typecheck.py` -> `check.py`, `typematch.py` -> `match.py`. The
old names survive **only** as the unchanged `TypeCast`/`TypeCheck`/`TypeMatch` class exports
from `my.typing` -- there are no `my.typing.typecast` (etc.) modules to import from anymore.

### Chamber decomposition: `Typist` -> `MyType` + cast/check/match

The monolithic `Typist` class is now a thin composition of three chambers -- `TypeCast`,
`TypeCheck`, `TypeMatch` -- plus a separate `MyType` model representing a parsed type
expression as an introspectable node (`.main`, `.args`, `.root`). The public singleton
`ty = typist = Typist.inst()` and its `ty.cast(...)` / `ty.check(...)` / `ty.match(...)`
surface are unchanged; what changed is internal structure -- each chamber gets its own test
module (`tests/typing/test_cast.py`, `test_check.py`, `test_match.py`) in place of one shared
`test_Typist.py`.

### `Decline` exception protocol replaces `suppress(Exception)` dispatch

The cast dispatch loop used to wrap every candidate transform in `suppress(Exception)`, so a
transform that genuinely crashed on its input was indistinguishable from one that
deliberately declined to handle it -- both silently advanced to the next candidate. A new
`Decline` exception (`my/typing/_common.py`) splits the two apart: a transform that cannot
handle a `(source, target)` pair raises `Decline` (or returns `None`, still honored), and only
`Decline` is caught before moving on. This drove 608 previously-swallowed latent crashes per
green test run down to 0, and the suite got roughly 30% faster as a side effect.

### TypeVar and union cast semantics changed (behavior break)

Constrained `TypeVar`s (e.g. `TypeVar('T', int, str)`) now resolve to the **union of all
constraints**, not an arbitrary single member. `TypeVar`s with a union bound
(`TypeVar('T', bound=int | str)`) resolve to that union directly. Union cast members are now
ranked by **fitness** instead of reverse declaration order, fixing a latent bug where a truthy
`bool` could get mis-cast ahead of a better-fitting member, and a `TypeError` in
`sort_options`. If any call site relied on "first union member wins" ordering or on a
constrained/bound TypeVar resolving to a single type, re-check it. (`d8c8d3a`, `834c91c`)

### PEP 695 generic parsing

Bare `TypeVar`s and `TypeVarTuple`/`ParamSpec` parameters now resolve and classify correctly
instead of raising or misclassifying by dead attribute names, so PEP 695 generic classes
(`class Foo[T]: ...`) parse cleanly through `MyType`.

### `pyrefly` typecheck gate

Static type checking is now enforced via `pyrefly check`, baselined under `[tool.pyrefly]` /
`[tool.pyrefly.errors]` in `pyproject.toml` and wired into CI (`.gitlab-ci.yml`'s
`Evaluate Python` job) and `AGENTS.md`. The baseline is 0 errors with 77 findings downgraded
to `warn` (not silenced) across documented categories -- see the comment block above
`[tool.pyrefly]` for the full breakdown. `my/types/Idx.py` and `my/types/IdxSpec.py` are
excluded from the gate entirely (unfinished, imports a pre-rename package name); their fate is
a separate, later decision.

### Removed

- The `sql` optional-dependency extra and its `sqlalchemy` dependency.
- `my.types.MyEnumRow`, an unused `sqlmodel`-era row-mapping helper.

### Fixed

- `[tool.pytest]` in `pyproject.toml` isn't a section pytest reads -- only
  `[tool.pytest.ini_options]` is, so `testpaths` was silently ignored. Fixing the header also
  activated a new `timeout = 15` (via `pytest-timeout`): any test exceeding 15s now fails fast
  with a stack trace instead of hanging until an infinite loop/recursion gets OOM-killed.
