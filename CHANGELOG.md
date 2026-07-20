# Changelog

All notable changes to `my-basis` are documented here.
The project has no prior tagged release -- `0.2.0` is the first tag, closing out a multi-month typing/subpackage overhaul that landed while the version stayed pinned at `0.1.0`.
Where a change is a behavior break rather than an internal fix, it's called out explicitly; mechanism and rationale live in the cited commit bodies, not repeated here.

## [0.9.0] - 2026-07-20

The release-readiness release toward a confident 1.0: a cluster of reproduced security and correctness fixes (each landed with a regression test), the `py.typed` marker, a lazy import facade that roughly halves the module count of a bare `import my`, and dependency/packaging cleanup.

### Security

- Removed a shell-injection RCE from `SystemUtils.print_in_color()` and `Command.execute()`/`execute_async()`: caller text was interpolated into a `shell=True` command string, so `$(...)`/backtick payloads executed.
  Both now run via an explicit argv with no shell (`create_subprocess_exec` on the async path).
- Enforced the `RegexStore` timeout on `Filesystem`'s raw-pattern search, which had bypassed the guard and could hang on a catastrophic-backtracking pattern.
- `Markdown` header scanning is now fence-aware: a `#` comment inside a fenced code block is no longer mistaken for a header.
- Cache pruning (`Cache`/`NestedCache`) is concurrency-safe -- it snapshots keys and `pop(..., None)`s instead of deleting while iterating.
- Telemetry defaults deny content capture, and the shared Logfire/OpenTelemetry setup no longer leaks a privacy boundary.

### Changed

- The `apis` and `files` facade leaves now load lazily (PEP 562 `__getattr__`): a bare `import my` no longer imports them or runs `apis`'s import-time side effects, cutting `import my` from ~1690 to ~1440 modules (~18% faster).
  One consequence: `Environment` snapshots `os.environ` on first `env` access rather than at `import my`.
  `from my import env` / `Markdown` / etc. are unchanged; `from my import *` and `hasattr(my, name)` still force the lazy names to load.
- The infra Jinja environment is likewise built on first `get_template()` / `JINJA` access instead of at import, so a bare `import my` no longer imports `jinja2` or stats the templates directory.
- **Breaking (pre-1.0):** renamed the generic type aliases `_Func`/`_Map`/`_Vec`/`_Struct` to `FuncT`/`MapT`/`VecT`/`StructT`, so no leading-underscore names appear in `__all__`.
- `ty.cast` no longer splits scalar strings on delimiters in container casts: `cast('a,b,c', list[str])` is `['a,b,c']`, not `['a', 'b', 'c']` (explicit over implicit).
- **Breaking:** two-digit apostrophe-years now pivot at 50 -- `'YY` greater than 50 resolves to the 1900s (`'99` -> 1999), 50 or below to the 2000s (`'50` -> 2050); previously every `'YY` became `20YY`.
- **Breaking (packaging):** the bundled resource package is nested under `my` (`my.data`) and no longer installs a top-level `data` namespace, closing a site-packages name collision.
  Resources are still reached through `INFRA_PATHS.data`; only code that imported the top-level `data` package directly is affected.
- `mdformat-front-matters` moved from the `[myst]` extra to core `dependencies`: `Markdown.render()`'s default template emits YAML frontmatter, so the plugin is required for correct core rendering (see Fixed).

### Fixed

- `Markdown.render(fix=True)` no longer breaks on a core-only install: the default template emits a `---...---` frontmatter block and `mdformat` raises on the then-unavailable `front_matters` extension; the plugin is now a core dependency.
- The optional-dependency `ImportError`s name the correct extra with an install hint: `GoogleSheet` reports `[google]` (was a copy-pasted `[metrics]`), `MetricUtils` reports `[metrics]`, both without the bogus `utils.` prefix.
- `ty.cast` coerces the element type in the scalar-wrap fallback (`cast('3', list[int])` -> `[3]`, not `['3']`), unwraps `Annotated[...]` targets (was returning `None`), and declines cyclic data with `Decline` instead of a bare `RecursionError`.
- `Markdown` notes/frontmatter now render instead of being silently discarded (they were emitted outside the Jinja block under `{% extends %}`).
- `NestedCache` propagates its configured `max_size`/`bucket_size` to child caches.
- `PickleCache.write()` is atomic (temp file + `os.replace`), with the pickle trust boundary documented.
- `Environment.set()` clears its cache for a previously-unset key (a set-after-absent key stayed stale).
- `MyEnum.write()` preserves empty-string member values.
- `SyntaxUtils.nested_replace()` reports `False` when it cannot mutate a tuple (it always returned `True`).
- `MetricUtils.setup_metrics()` no longer crashes clearing a non-empty metrics directory, and sub-millisecond durations are recorded instead of dropped.
- `SystemUtils` logging uses a module logger (not root), accepts `**kwargs`, and materializes `map` messages to strings.
- The `year` regex and the ISO-date `y` block are open through the 21st century (dates from 2027/2030 onward match again); `md_url` captures targets with balanced inner parens.
- The `regex-storefront` console script no longer crashes on construction (mutable-default `RegexStore`).

### Added

- `my/py.typed` marker: the `Typing :: Typed` classifier is now true, so consumers' type checkers read basis's types instead of `Any`.
- `FileCache.delete()` for single-item removal.

### Removed

- Unused core dependencies `identify`, `toolz`, `tqdm`; `dotenv` repinned to `python-dotenv`.
- Dead `Idx`/`IdxSpec` modules and the `my.text`/`my.type` deprecation shims.

### Docs / CI

- README corrected: PyPI publication status, dependency scale, the flagship `cast` example, and the restored PyPI badges.
- `task docs` builds again (added `sphinx.ext.intersphinx` and its mapping).
- The Publish job asserts the git tag matches the `pyproject` version.
- Documented the intentional `utils = Utils` aggregation (`my.utils` is the facade class, deliberately shadowing the submodule) and pinned it with a guard test, so it is not "de-shadowed" by mistake.
- Documented the five optional extras (`metrics`/`google`/`myst`/`terminal`/`aiohttp`) in the README with an install table.
- Added the missing `apis.Filesystem` and `types.Platform` reference pages; the `Typist` page now renders its inherited `cast`/`check`/`match` methods.
- Corrected the subpackage dependency-tree docstring (added the `infra` root and the `apis`→`regex` / `regex`→`typing` edges).

### Tests

- Hardened the 0.8.3 performance/security claims with real coverage: `Buffer`'s `REGEX_TIMEOUT` firing, `md_url` ReDoS resistance, `pair_list()` cache invalidation, and console-script smoke tests.
- Made the suite hermetic (`conftest` no longer writes under `~/local/logs`) and stopped the `Environment` tests leaking classvar state across the run.

## [0.8.3] - 2026-07-11

Performance and security release for MEMY-175 wikiparse polish wave 2.

### Performance

- `Span._fast(a, b)` trusted constructor bypassing all type coercion and validation for hot iterators (Buffer, MatchData). +45% throughput in wikiparse.
- `Buffer._version` counter + `_pair_cache` dict + `pair_list()` cached method for read-only pair iteration.
- `raw_pair_iterator` gained `strict: bool = True` parameter for cached/non-strict modes.
- `_shift_pair_cache` method for incremental cache updates (infrastructure, not yet enabled).

### Security

- `REGEX_TIMEOUT = 10.0` guard on Buffer's 3 hot iterator `rgx.search()` calls (ReDoS protection).
- Fixed `md_url` ReDoS vulnerability (cubic backtracking on spaces) via possessive `*+` quantifiers in `common_rgxs.py`.

## [0.8.2] - 2026-07-11

Release-machinery and README polish; no library behavior changes.

### CI/CD

- Added a PyPI OIDC trusted-publishing job and expanded the project URLs.
- Decoupled Publish from Evaluate, capped job timeouts, and skipped lint on tag pipelines.
- Normalized `.gitlab-ci.yml` to the house yamlfmt (4-space indent).

### Fixed

- `Predicate`: removed the `serialize` advertisement and its dead xfail tests.

### Docs

- README: dropped stray backticks, fixed the badges, removed the `{align}` directive, and added the logo.

## [0.8.1] - 2026-07-10

First PyPI release (`pip install my-basis`).

### Fixed

- `Markdown.walk()` now honors its documented `-1` unlimited-depth sentinel: the recursion guard excluded `-1`, silently capping every default `walk()`/`tree`/`prose_tree` traversal at two levels.
  Consumers that walked deep documents (e.g. wikiparse's nested `###` subsections) saw nodes below level 2 skipped.

### Packaging

- Declared `license = "MPL-2.0"` (SPDX) and `license-files` in `pyproject.toml` so the published wheel carries the license metadata that was previously only in the `LICENSE` file.

## [0.2.0] - 2026-07-02

### Subpackage & module renames

`my.text` split three ways: regex symbols (`RegexStore`, `RegexParser`, etc.) moved to `my.regex`; `Buffer`/`Span` moved to `my.types`; `Markdown` moved to `my.files`.
`my.type` was renamed wholesale to `my.typing`.
Both old import paths still work via deprecation shims (`my/text/__init__.py`, `my/type/__init__.py`) that re-export the current surface and raise a `DeprecationWarning` on import -- migrate off them before they're removed.
Not every old symbol has a shim: `my.text`'s `atom`/`debug_regex` free functions and `my.type`'s `TimeType` alias had no unambiguous modern equivalent and were dropped outright; see the shim docstrings for the full accounting.

Within `my.typing`, three files were also renamed to a shorter, chamber-oriented convention: `typecast.py` -> `cast.py`, `typecheck.py` -> `check.py`, `typematch.py` -> `match.py`.
The old names survive **only** as the unchanged `TypeCast`/`TypeCheck`/`TypeMatch` class exports from `my.typing` -- there are no `my.typing.typecast` (etc.) modules to import from anymore.

### Chamber decomposition: `Typist` -> `MyType` + cast/check/match

The monolithic `Typist` class is now a thin composition of three chambers -- `TypeCast`, `TypeCheck`, `TypeMatch` -- plus a separate `MyType` model representing a parsed type expression as an introspectable node (`.main`, `.args`, `.root`).
The public singleton `ty = typist = Typist.inst()` and its `ty.cast(...)` / `ty.check(...)` / `ty.match(...)` surface are unchanged; what changed is internal structure -- each chamber gets its own test module (`tests/typing/test_cast.py`, `test_check.py`, `test_match.py`) in place of one shared `test_Typist.py`.

### `Decline` exception protocol replaces `suppress(Exception)` dispatch

The cast dispatch loop used to wrap every candidate transform in `suppress(Exception)`, so a transform that genuinely crashed on its input was indistinguishable from one that deliberately declined to handle it -- both silently advanced to the next candidate.
A new `Decline` exception (`my/typing/_common.py`) splits the two apart: a transform that cannot handle a `(source, target)` pair raises `Decline` (or returns `None`, still honored), and only `Decline` is caught before moving on.
This drove 608 previously-swallowed latent crashes per green test run down to 0, and the suite got roughly 30% faster as a side effect.

### TypeVar and union cast semantics changed (behavior break)

Constrained `TypeVar`s (e.g. `TypeVar('T', int, str)`) now resolve to the **union of all constraints**, not an arbitrary single member.
`TypeVar`s with a union bound (`TypeVar('T', bound=int | str)`) resolve to that union directly.
Union cast members are now ranked by **fitness** instead of reverse declaration order, fixing a latent bug where a truthy `bool` could get mis-cast ahead of a better-fitting member, and a `TypeError` in `sort_options`.
If any call site relied on "first union member wins" ordering or on a constrained/bound TypeVar resolving to a single type, re-check it. (`d8c8d3a`, `834c91c`)

### PEP 695 generic parsing

Bare `TypeVar`s and `TypeVarTuple`/`ParamSpec` parameters now resolve and classify correctly instead of raising or misclassifying by dead attribute names, so PEP 695 generic classes (`class Foo[T]: ...`) parse cleanly through `MyType`.

### `pyrefly` typecheck gate

Static type checking is now enforced via `pyrefly check`, baselined under `[tool.pyrefly]` / `[tool.pyrefly.errors]` in `pyproject.toml` and wired into CI (`.gitlab-ci.yml`'s `Evaluate Python` job) and `AGENTS.md`.
The baseline is 0 errors with 77 findings downgraded to `warn` (not silenced) across documented categories -- see the comment block above `[tool.pyrefly]` for the full breakdown.
`my/types/Idx.py` and `my/types/IdxSpec.py` are excluded from the gate entirely (unfinished, imports a pre-rename package name); their fate is a separate, later decision.

### Removed

- The `sql` optional-dependency extra and its `sqlalchemy` dependency.
- `my.types.MyEnumRow`, an unused `sqlmodel`-era row-mapping helper.

### Fixed

- `[tool.pytest]` in `pyproject.toml` isn't a section pytest reads -- only `[tool.pytest.ini_options]` is, so `testpaths` was silently ignored.
  Fixing the header also activated a new `timeout = 15` (via `pytest-timeout`): any test exceeding 15s now fails fast with a stack trace instead of hanging until an infinite loop/recursion gets OOM-killed.
