# DESIGN: Per-call cast-flag context

> **Status:** implemented, per the recommendation below, across two staged commits (basis-13):
> `d924116` (`CastFlags` + threading, behavior-identical) and the dispatch-scan memoization
> that follows it. Direct singleton mutation remains the default source; nothing is deprecated.

## Problem

> `Typist`'s cast flags (`firsts` / `atomics` / `splits` / `wraps`, `Typist.py` "Cast
> configuration flags" block) are instance fields on the global singleton, and the transforms
> read them **live** mid-cast through `Transform.ty` (`cast.py:591, 610, 824, 889, 982`). Two
> consequences:
>
> 1. **Action at a distance.** Any caller mutating `ty.splits = …` changes every other
>    caller's cast results process-wide. The suite already needs a save/restore fixture
>    (`flex_typist` in `tests/typing/test_cast.py`) just to survive its own flag tests.
> 2. **No memoization, ever.** A cast's output depends on ambient mutable state, so results
>    can never be cached — every repeated `cast('a.b', list[str])` re-runs the full dispatch.

## Proposal

### 1. A frozen `CastFlags` model

> A tiny frozen (hashable) pydantic model holding the four booleans, with a
> `CastFlags.preset('strict' | 'basic' | 'flex')` constructor absorbing today's
> `Typist.preset()` dict bundles. `Typist` keeps its four fields — they become the *default
> source* the per-call snapshot is taken from.

### 2. Resolve once, at the public entry points

> `TypeCast.cast()` (and the `Typist.cast` / `upper_cast` / `multicast` facades) grow an
> optional `flags: CastFlags | str | None = None` parameter, resolved exactly once at entry:
> an explicit argument wins; otherwise snapshot the global singleton's current field values.
> This is the compatibility story: direct `ty.splits = …` mutation keeps working as the
> process-wide default — it just stops being readable *mid-flight*, so a cast sees one
> consistent flag set from start to finish.

### 3. Thread through `Transform`

> `Transform` is already the per-cast ephemeral state carrier (data, `t0`, `t1`), so the
> resolved snapshot becomes one more field on it. Transforms swap `self.ty.wraps` for
> `self.flags.wraps`. The one real cost: nested casts currently re-enter through the
> module-level `tyt.cast(...)`, so the snapshot must be forwarded explicitly at the recursion
> seams — `Transform.to` / `.proxy` / `.by`, `to_union`, and the handful of direct
> `tyt.cast` call sites inside `cast.py`. They are few and mechanical; an explicit field is
> preferred over a `ContextVar` because it keeps casts pure functions of their inputs (a
> `ContextVar` would re-introduce ambient state, just better-scoped).

### 4. What this newly permits

> - **Memoization:** with `CastFlags` frozen and hashable, `(t0, t1, flags)` → transform
>   candidate list is immediately cacheable, and full result caching becomes possible for
>   hashable data. The dispatch scan (`_TRANSFORMS` filter + specificity sort) currently
>   reruns on every single cast — including each member attempt inside a union cast.
> - **Concurrency safety:** two threads (or an agent pipeline) can cast at different
>   strictness tiers without racing on the singleton.
> - **Test hygiene:** the save/restore fixture reduces to `cast(..., flags='flex')`.
> - **Typecheck surface (pyrefly):** the `pyproject.toml` baseline cites deep TypeVar-bound
>   tracking in `MyType` as a warn-tier cause. Per-call flags don't fix those bounds
>   directly, but removing live singleton reads shrinks the `Any`-typed flow into transforms
>   (`self.ty` resolves through the untyped `_TypingBase._ty()` bridge today), and a typed
>   `CastFlags` retires the `dict[str, bool]` preset bundles — both trim the surface pyrefly
>   currently has to guess at. Expect a modest suppression-count drop, not a tier change.

## Recommendation

> Do it, in two commits: (1) introduce `CastFlags` + the `flags=` parameter with
> entry-point snapshotting and `Transform` threading — behavior-identical by construction
> when no caller passes flags, since today no code mutates flags mid-cast; (2) add the
> dispatch-scan memoization keyed on `(t0, t1, flags)`, which is the cheap, high-leverage
> cache — defer full result caching until profiling justifies it. Keep direct singleton
> mutation supported indefinitely as the default source; deprecate nothing.
