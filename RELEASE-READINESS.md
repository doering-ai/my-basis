---
title: myBasis 1.0 Release-Readiness Review & Remediation Tree
status: draft
date: 2026-07-18
reviewer: claude-fable (10-agent adversarial fan-out)
scope: libs/basis @ v0.8.3 (+16 unreleased commits on main)
---

# myBasis 1.0 Release-Readiness Review & Remediation Tree

> **Verdict up front:** **Not ready for a confident public 1.0 sign-off yet — but the gap is a punch-list, not a rewrite.** The core engineering is genuinely strong (3637 green tests in 2.7s, disciplined structure, thorough docstrings, real ReDoS/`walk()` fixes that hold up under attack).
> What blocks sign-off is a cluster of *sharp, individually-cheap* defects: a handful of reproduced correctness/security bugs, several release-machinery gaps, a false `Typing :: Typed` claim, a README that misdescribes reality, and the dependency-bloat problem the maintainer already flagged.
> Every finding below was reproduced live or read from source — nothing is speculative.

This document is the response to that review: a **tree of tasks** (tentative `basis-NN` SIDs, continuing the existing campaign — `basis-06`…`09` are already referenced in `pyproject.toml`; these map to future `MEMY-N` Plane cards) to systematically close every criticism worth fixing.
The **import / dependency-bloat cluster is developed in full as the worked first slice** (§4), as the template for how the remaining slices execute.

______________________________________________________________________

## 0. Execution log — 2026-07-18 (first pass, operator-directed)

The operator triaged the tree (19 tasks commented) and directed a bold first pass.
Everything below **landed and passed the full gate** (`pytest` 3636 passed + 21 subtests + 2 snapshots · `ruff check`/`format` clean · `pyrefly` 0 errors · wheel rebuilt) and is uncommitted in the working tree for review.

**✅ Done this pass**

- `basis-D1` — dropped `identify`, `toolz`, `tqdm` (zero usage) from core deps.
- `basis-D2` — repinned `dotenv` → `python-dotenv>=1.0.1` (the 0.9.9 trampoline is gone; `import dotenv` unchanged).
- `basis-D3` — added `my/py.typed`; **verified it ships in the rebuilt wheel** (`Typing :: Typed` is now true).
- `basis-P3` — deleted `my/types/Idx.py` + `IdxSpec.py` (Sublime-Headers copies; concept belongs in `arch`) and their pyrefly excludes.
- `basis-A4` — deleted the `my.text` / `my.type` shims + their tests (pre-1.0, zero consumers → no deprecation period needed).
- `basis-A5` — added `MetricUtils` / `metric_utils` to `my.__all__` (closed the facade drift).
- `basis-M7` — re-enabled the `exclude-newer = "10 days"` supply-chain buffer (uv accepts it; resolves to a concrete cutoff).
- `basis-T4` — removed the false `Predicate.serialize` xfail claim from the pyrefly comment.
- `basis-M4` — added a `tag == pyproject version` guard to the Publish job's `before_script` (blocks mislabeled uploads).
- `basis-C3` — **thread-safety**: `Cache.prune` / `NestedCache.prune`+`delete` now snapshot keys and `pop(..., None)` instead of `del`-while-iterating.
  Lockless, crash-free (dict ops are atomic under the GIL — no lock needed, per the operator's instinct).
  New regression tests: a concurrent 8-thread hammer + an over-prune case.
- `basis-C4` — **fence-aware Markdown**: a `#` comment inside a ```` ``` ````/`~~~` fence is no longer mistaken for a header.
  Position-preserving `_mask_fences` pre-pass in `parse()`/`reparse_prose()`, sentinel restored on kept text.
  New regression tests for backtick + tilde fences.
- `basis-M1` — **resolved by operator**: the account-wide classic PyPI token was deleted.
  Trusted-publishing-only is now the real posture.

**🧭 Decisions recorded (supersede the original tree)**

- `basis-D10` → **KEEP numpy.** Releasing ASAP; bite the 60 MB (numpy is a near-universal transitive anyway).
  Benchmark gate dropped.
- `basis-A` (aliases) → **KEEP the shorthand.** The operator's `from my import ut, ty` ergonomics *are* the product; for an opinionated personal-utility lib the "external cognitive load" argument is weak.
  The surviving fixes: aliases must not get their own alphabetical doc entries (they become referenced values in the canonical object's docstring — folds into the `basis-X` docs aesthetic), and `basis-A1`'s `my.utils` **shadow is still a real bug** (it silently overwrites the submodule, distinct from a harmless alias).
- `basis-A2` → export only the canonical spellings with intent (`Typist`, `Utils`, …); keep the aliases, treat-as-aliases in docs.
- `basis-A3` → rename the generic type variants `_Func/_Map/_Vec/_Struct` (they're meant to be *used* — the parametrizable forms) to **`FuncG/MapG/VecG/StructG`** (`G` = generic; no leading-underscore collision).
  Staged: 29 internal sites.
- `basis-M` (machinery) → **CI/CD-only releases**; the "over-diagnosed" security framing and the local-publish path are retired from the plan (see reworked slice below).

**📋 Staged next (with open questions in the chat report)**

- `basis-X1` / `basis-D11` / `basis-X` — README + docs overhaul: real dep numbers, example-first "cropped-snippet" aesthetic (ugly-vs-pretty side-by-side), shrink the logo, add an example gif/carousel, vision-verify the render; ensure no older module is under-docced and every import-tree node has a page.
- `basis-P2` — remove the *test-copy* of `importas.yaml` from the wheel, and make the canonical/latest `importas.yaml` the source for the `myPython` Sublime syntax (cross-repo; needs investigation of the sublime side).
- `basis-X3` — fix `task docs` (add `sphinx.ext.intersphinx` + mapping) and provision Read the Docs (operator has accounts; `docs.doering.ai` is an option too).
- `basis-A1` / `basis-A3` — de-shadow `my.utils` (1 consumer site: `means/cli/report.py`) and roll out the `FuncG` rename.
- `basis-M2` — assessed: "branch must be green to publish" is **true by convention, not enforced on the tag pipeline** (tag pipelines skip Eval/Test; `Publish` has `needs: []`).
  For a CI-only single-maintainer flow the residual risk is low; recommend documenting it as accepted rather than building a flaky pipeline-status gate.
  `basis-M4` (the real mislabel footgun) is now closed.
- `basis-M8` — surface non-fatal CI failures (e.g. secret-detection) through Logfire — nice-to-have.
- `basis-C5`–`C17`, `basis-P1`/`P2`, `basis-X*` — remaining correctness/packaging/docs items.

**✅ Second pass (same day) — committed + pushed**

- `basis-A3` — renamed the generic aliases `_Func/_Map/_Vec/_Struct` → **`FuncT/MapT/VecT/StructT`** across all 8 sites (operator chose `T` for "types" over `G`).
- `basis-X3` (build) — `task docs` now builds: added `sphinx.ext.intersphinx` (+ python/pydantic/numpy/more-itertools mapping) and dropped `--nitpicky` from the gate to match Read the Docs.
  RTD *provisioning* still pending the operator's account import.
- `basis-P2` / regex-storefront — fixed a real crash in the `regex-storefront` console script (mutable-default `RegexStore` → `threading.Lock` deep-copy failure) plus a stray `breakpoint()`, added smoke tests, then regenerated the `importas` alias regex (520 aliases; was a stale 487-subset) and spliced it into `subl/syntaxes/python/myPython.sublime-syntax` with a `{0,3}`→`{0,4}` lookahead widening.
  There is only **one** `importas.yaml` (basis is canonical) — no test-copy to delete.
- Policy — added a *voice* convention (calmly hyperbolic enthusiasm for primary repo docs) to `corpus/policies/markdown_style.md`.
- **Deferred (needs operator judgement):** `basis-X1` / the gifs — the sandtui pixel-art motif is viable but needs real Rust build work first (the "TS sibling" doesn't exist; its font can't render code punctuation, vine growth is dormant, there's no GIF export).
  See the chat report.
  **(Superseded 2026-07-18: the gifs were built via a Node/`@napi-rs/canvas` pipeline in `apps/doering-ai`; two hero clips — `ty.cast` and `Markdown.parse` — are now wired into the README.)**

**✅ Third pass — 2026-07-18 (C-series correctness/security core, orchestrated Sonnet worktree wave)**

Six isolated worktrees (one per file-cluster), each an independent Sonnet agent that reproduced → fixed → regression-tested → ran the full suite; merged into `main` after review.
Final gate: **3681 passed** (baseline 3639 + 42 new regression tests) · `pyrefly` 0 errors · `ruff` clean.

- `basis-C1` / `basis-C2` ⭐ — **shell-injection RCEs removed** from `SystemUtils.print_in_color()` and `Command.execute()`/`execute_async()`: no more `shell=True` string interpolation; explicit argv (`create_subprocess_exec` on the async path).
  Regression tests encode the actual `$(touch marker)` exploit.
- `basis-C8` — SystemUtils logging: module logger (not root), `**kwargs`, materialized `map` messages.
- `basis-C9` / `C10` / `C12` — `ty.cast`: element coercion in the scalar-wrap fallback (`['3']` → `[3]`), `Annotated[...]` unwrap, cyclic-data → `Decline` (not `RecursionError`).
  MEMY-325 no-split preserved.
- `basis-C6` — `Markdown` notes/frontmatter now render (were discarded outside the Jinja block under `{% extends %}`).
- `basis-C13` / `C15` — `NestedCache` child-config propagation; atomic `PickleCache.write()` + documented pickle trust boundary.
- `basis-C11` / `C14` / `C16` — `MyEnum.write()` empty-string; truthful `nested_replace()` tuple return; `MetricUtils.setup_metrics()` rm-crash + sub-ms drop.
- `basis-C5` — `year` **and** the ISO-date `y` block opened through the 21st century (twin year-bomb closed); `md_url` balanced inner parens.
- `basis-C17` — regex timeout enforced on `Filesystem`'s raw-pattern search (an 8 s hang before the fix).
- `basis-X1` (docs subset) — README truth-fixes: `B6` (claimed "not published"; live on PyPI since 0.8.1), `B7` (wrong `list[str]` example), the refuted dep-scale figure, restored PyPI badges.
- `basis-X2` — CHANGELOG: added Unreleased + the missing 0.8.2 entry.

**🧭 Rejected / deferred with evidence (stop-and-report discipline held):**

- `basis-C7`(a) — the import-time `os.environ` snapshot is **intentional design** (the suite patches `Environment._ENVIRON`, not `os.environ`; `set()` is the sanctioned mutation path).
  Only the `set()`-cache-staleness half was a bug — fixed.
- `basis-C5` (century pivot) — ⚠ **operator decision:** apostrophe-years always resolve `20xx` (`'99` → 2099).
  A pivot threshold (`'99` → 1999) is a product call, not a regex bug; left as-is pending a ruling.

**Remaining (Wave 2, structural — deliberately not run blind in parallel):** `basis-A1` (de-shadow `my.utils`), `basis-P1` (un-claim top-level `data`), `basis-D4`–`D6` (lazy facade).
Plus machinery `basis-M5` (version bump at release), test hardening `basis-T1`/`T2`, docs `basis-X5`/`X6`.

**✅ Fourth pass — 2026-07-19 (operator decisions on A1/P1/C5; two Sonnet worktrees + one launcher docs edit)**

Final gate: **3699 passed** · `pyrefly` 0 errors · `ruff` clean.

- `basis-A1` — **resolved as docs, not a code change (operator ruling).** The `utils = ut = Utils` aggregation is intentional (means and other consumers do `from my import utils as ut` and call ~11 aggregated methods); dropping `utils` would break them.
  Documented the design in `my/utils/__init__.py` and pinned it with a guard test (`tests/utils/test_utils_facade.py`).
- `basis-P1` — **`data/` nested under `my` (`my.data`) (operator chose "nest").** `git mv` + anchor rewire in `my/infra/constants.py`; `module-name = ["my"]`, `namespace` dropped.
  Wheel verified to ship `my/data/` (templates + yamls + snapshots) with no top-level `data/`.
  Incidental: fixes a previously-broken `docs/conf.py` template path.
  Follow-up: `my/data/snapshots/test_RegexStore.ambr` is a dead orphan (real syrupy snapshots live in `tests/regex/__snapshots__/`) — safe to delete.
- `basis-C5` (century pivot) — **pivot at 50 (operator ruling): `'YY > 50` → 1900s (`'99` → 1999), `≤ 50` → 2000s (`'50` → 2050).** Was unconditionally `20YY`.

**Still open for a future dedicated effort:** `basis-D4`–`D6` (lazy facade — highest value/risk, needs a cross-consumer import smoke test), `basis-M5` (version bump at release), `basis-T1`/`T2`, `basis-X5`/`X6`.
Consumer-adoption watch (all pinned to the `stable` tag today, so not live): the `Command` `pipe`/`out` rewrite (`out` preserves append; `pipe` now sequential-buffered) and the C9/C14 behavior changes.

**✅ Fifth pass — 2026-07-20 (D/T/X sections, orchestrated Sonnet worktree wave)**

Three disjoint-file Sonnet worktree agents (extras/imports, docs, tests), each green in isolation, merged into `main`; combined gate: **3728 passed** · `ruff` clean · `pyrefly` 0 errors.

- `basis-D7` — the missing-dependency `ImportError`s now name the *right* extra: `GoogleSheet` reports `[google]` (was a copy-pasted `[metrics]`), `MetricUtils` reports `[metrics]`, both without the bogus `utils.` prefix and with a `pip install my-basis[<extra>]` hint + a docstring pointer.
  Regression test asserts the `[google]` message.
- `basis-D8` — **latent core-install crash closed.** The default `Markdown.md.jinja` emits a `---...---` frontmatter block unconditionally, and `mdformat` raises `KeyError` on a requested-but-absent extension, so `Markdown.render(fix=True)` crashed on a bare-core install (where `mdformat-front-matters` lived only in `[myst]`).
  Promoted `mdformat-front-matters` to core `dependencies`; the wheel METADATA now carries it unconditionally.
- `basis-D9` — documented all five extras (`metrics`/`google`/`myst`/`terminal`/`aiohttp`) in the README with an install table.
- `basis-T1` — the 0.8.3 "Performance & Security" claims are now actually tested: `Buffer.REGEX_TIMEOUT` firing on `(a|a)+b`, `md_url` ReDoS resistance (pins the possessive `*+` fix), `pair_list()` cache correctness/identity/invalidation, and a `sync-docs` console-script smoke test.
- `basis-T2` — `conftest` is hermetic: `MY_LOGS` sinks to a temp dir unconditionally (the fleet-wide `MY_LOGS=~/local/logs` export made the "respect existing" variant non-hermetic), so the suite no longer writes under `~/local`.
- `basis-T3` — reproduced then fixed: the `set()`-family tests leaked keys into the shared `Environment._ENVIRON` classvar; an autouse snapshot/restore fixture now isolates every test.
- `basis-X5` — backfilled the missing `apis.Filesystem` and `types.Platform` reference pages and added `:inherited-members: BaseModel` to the `Typist` page so `cast`/`check`/`match` render (scoped to `BaseModel` to keep the `--fail-on-warning` build clean).
- `basis-X6` — corrected the stale subpackage dependency-tree docstring: added the omitted `infra` root and the `apis`→`regex`/`regex`→`typing` edges, fixed depth, and footnoted `data`/`scripts` rather than fabricating import edges.

**Still open:** `basis-D4`–`D6` (lazy facade — the maintainer's named priority; the one structural item, deferred to run as a careful sequenced change with a facade smoke test) and `basis-M5` (version bump at release, operator-gated).

______________________________________________________________________

## 1. How this was produced

Ten explicitly Sonnet-tagged subagents, in two coordinated waves plus a verification pass:

- **Wave 1 — the worked example (imports/deps):** empirical import-graph timing, per-dependency necessity audit, fresh bare-install probe (built the wheel, installed with zero extras), and an API-surface/facade critique.
- **Wave 2 — broad axes:** test-suite audit, docs/consistency audit, hostile correctness review of the typing engine, hostile review of regex/files/utils, CI/release-machinery audit, and a downstream blast-radius survey across all 11 ecosystem consumers.
- **Wave 3 — verification:** the orchestrator re-ran the sharpest claims directly against the tree (py.typed absence, dead deps, the 2027 year bomb, the shell-string injection, the facade shadow, env staleness, `cast('3', list[int])`, Markdown fence corruption, mdformat frontmatter, the wrong-extra error message, version/tag drift) — all confirmed.

Full transcripts under the job scratch dir; this file is the durable synthesis.

______________________________________________________________________

## 2. Severity synthesis (cross-axis)

### 2.1 Blockers — must clear before a confident public 1.0

| #   | Finding                                                                                                                                                                                                                                                                            | Evidence (verified)                                                                                                    | Slice      |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------- |
| B1  | **Shell injection (RCE) in `SystemUtils.print_in_color()`** — `sbp.run(f'zsh -c \'print -P "{text}"\'', shell=True)` with unsanitized `text`                                                                                                                                       | marker-file RCE reproduced                                                                                             | `basis-C1` |
| B2  | **`Command.execute()` shell injection** — hand-rolled `_shell_quote` (double-quote only) + `shell=True`; `$(...)` substitution runs                                                                                                                                                | `touch`-marker RCE reproduced                                                                                          | `basis-C2` |
| B3  | **Unsynchronized global type caches — structural data race** — `MyType.PARSE_CACHE`/`MATCH_CACHE` are process-wide `ClassVar` singletons over plain dicts; `Cache.prune()` does `del self.data[key]` while iterating `keys()`, no lock anywhere; behind *every* `cast/check/match` | source-confirmed (zero locking in `my/caches/`); subagent hit an 8-thread `KeyError`, intermittent (narrow GIL window) | `basis-C3` |
| B4  | **`Markdown.parse()` corrupts docs with `#`-comment code fences** — fabricates a node titled from the comment, misnests following sections                                                                                                                                         | 2-node/`'a comment'` title reproduced                                                                                  | `basis-C4` |
| B5  | **`py.typed` absent while classifier claims `Typing :: Typed`** — every consumer's type checker sees `Any`                                                                                                                                                                         | `find` empty in source + wheel                                                                                         | `basis-D3` |
| B6  | **README says "not yet published to PyPI"; it has been since 0.8.1**                                                                                                                                                                                                               | PyPI JSON API: 0.8.1/0.8.2/0.8.3 live                                                                                  | `basis-X1` |
| B7  | **README flagship quickstart is wrong** — `ty.cast('a,b,c', list[str])` returns `['a,b,c']`, not `['a','b','c']` (deliberate MEMY-325 change)                                                                                                                                      | reproduced                                                                                                             | `basis-X1` |
| B8  | **Local publish path bypasses all CI/OIDC guardrails** — `Taskfile.dist.yaml pkg:publish` uses long-lived `PYPI_TOKEN`; "trusted-publishing only" is false if any classic token still exists                                                                                       | operator must verify/revoke on PyPI                                                                                    | `basis-M1` |
| B9  | **`year` regex hardcodes an upper bound of 2026** — every natural-language date from 2027 silently drops its year (< 6 months out)                                                                                                                                                 | `C.search('year','2027') == {}` reproduced                                                                             | `basis-C5` |

### 2.2 High — strongly should fix

- **`mdformat`/`myst` split silently corrupts frontmatter** on a core-only install: `Markdown.render(fix=True)` (the default) destroys the YAML block its own template emits; no test catches it. (`basis-D8`) — reproduced: default mangles, `extensions={'front_matters','myst'}` round-trips.
- **`Markdown` `notes`/frontmatter is dead Jinja** — emitted outside any `{% block %}` under `extends`, so it never renders in *any* environment; documented feature silently drops data. (`basis-C6`)
- **`my.utils` facade shadow is a live runtime bug**, not the "static-only" artifact `pyproject.toml` claims: `import my.utils as u` → the `Utils` *class*; `hasattr(u,'iter_utils')` is `False`. (`basis-A1`) — reproduced.
- **`import my` has unconditional import-time side effects** for all 11 consumers: `load_dotenv()` walks ancestor dirs; `os.environ` is snapshotted once (vars set after import are invisible to `my.env` — reproduced); a YAML is read; ~11 paths resolved. (`basis-D5`, `basis-C7`)
- **Eager-but-guarded `metrics`/`google` imports tax every `import my`** — when installed they front-load ~37% of import cost; `logfire`'s pydantic entry-point plugin adds another ~34% (~228ms) the instant basis defines its first `BaseModel`. (`basis-D6`)
- **`GoogleSheet` missing-dep error names the wrong extra** — raises `` requires the optional `[metrics]` dependency `` (should be `[google]`), with a copy-pasted `utils.` prefix; no source of truth anywhere names `[google]`. (`basis-D7`) — confirmed in source.
- **`SystemUtils` logging cluster** — `getLogger()` grabs the *root* logger (library anti-pattern); `info/warn/error` signatures use `kwargs` not `**kwargs` (raise `TypeError` on the documented call); `log()` passes a live `map` object as the message (`<map object …>`). (`basis-C8`)
- **`ty.cast('3', list[int])` → `['3']`** — the "wraps" fallback skips element coercion; a `list[int]` silently contains a `str`. (`basis-C9`) — reproduced.
- **Publish has no test gate** — tag pipelines skip Evaluate/Test, `Publish PyPI` has `needs: []`, secret-detection never runs on tag pipelines, `pypi` approval is self-approval.
  Convention, not enforcement. (`basis-M2`)
- **0.8.3 "Performance & Security" release claims are untested** — no test fires Buffer's `REGEX_TIMEOUT`, no `md_url` ReDoS regression, no `pair_list()` cache-invalidation test. (`basis-T1`)
- **`task docs` fails outright** — 607 nitpick warnings-as-errors from a missing `intersphinx_mapping`; the documented build command is broken. (`basis-X3`)

### 2.3 Medium / Low — batched, non-rabbit-hole

Correctness: `Annotated[...]` cast returns `None` (`basis-C10`); `MyEnum.write()` loses `''` values (`basis-C11`); cyclic *data* → bare `RecursionError` (`basis-C12`); `Environment.set()` cache never clears for previously-unset keys (`basis-C7`); `NestedCache` children ignore configured `max_size`/`bucket_size` (`basis-C13`); `SyntaxUtils.nested_replace()` returns `True` on tuples it never mutates (`basis-C14`); `PickleCache.write()` non-atomic + undocumented pickle trust boundary (`basis-C15`); `MetricUtils.setup_metrics()` `rm -rf` without `shell=True` always crashes, sub-ms timings dropped (`basis-C16`); `RegexStore` timeout bypassed by raw-pattern accessors used in `Filesystem` (`basis-C17`); `md_url` truncates targets with inner `)`, apostrophe-year always 20xx (`basis-C5`).
Dead code: `Idx.py`/`IdxSpec.py` unimportable yet shipped (`basis-P3`); `my.text`/`my.type` shims undocumented, no removal target (`basis-A4`).
Docs: CHANGELOG missing 0.8.2 + Unreleased (`basis-X2`); RTD 404 / badges (`basis-X4`); `Typist` docs omit `cast/check/match` (missing `:inherited-members:`) + missing `Platform`/`Filesystem` pages (`basis-X5`); stale dependency-tree docstring (`basis-X6`).
Tests: non-hermetic `conftest` writes `~/local/logs` at import (`basis-T2`); singleton leak in `test_Environment` (`basis-T3`); false `Predicate.serialize` xfail comment in `pyproject.toml` (`basis-T4`); console-scripts at 0% coverage (`basis-T1`).
Machinery: `dist/` holds stale mixed-version artifacts (`basis-M3`); no tag==version assert (`basis-M4`); version not bumped past 0.8.3 despite 16 commits (`basis-M5`); dead `.pre-commit-config.yaml` shadowed by `prek.toml`, orphaned `.yamlfmt`/`.taplo`/`.plumber` configs (`basis-M6`); `exclude-newer` "critical" comment vs commented-out state (`basis-M7`); secret-detection off on MRs (`basis-M8`); no scheduled base-image rebuild (`basis-M9`).
API: naming sprawl `ty/tyc/tym/tyt/typist/Typist` etc. (`basis-A2`); underscore names in `__all__` (`basis-A3`); facade drift `MetricUtils` missing from `my.__all__` + no regression test (`basis-A5`).

______________________________________________________________________

## 3. Proposed task tree

The `1.0` campaign, seven slices. **`basis-D*` (the dependency slice) is the worked first slice**, developed in full in §4.
Each leaf carries a rough cost and a blast-radius note from the consumer survey.
`⭐` = keystone; `⚠` = needs a human decision or is the one genuine rabbit-hole.

```
basis-1.0  myBasis 1.0 Release-Readiness Campaign
│
├── basis-D  ⭐ Dependency & Import Slice   ── the worked example, §4
│     ├── basis-D1  Drop dead deps: identify, toolz, tqdm            (pyproject only; 0 sites)
│     ├── basis-D2  Repin dotenv → python-dotenv                     (1 line; import unchanged)
│     ├── basis-D3  ⭐ Ship my/py.typed + verify wheel inclusion     (near-pure bug fix)
│     ├── basis-D4  Lazy facade (PEP 562 __getattr__) for apis+files (leaf pkgs; quickstart intact)
│     ├── basis-D5  Kill import-time side effects behind the facade  (folds into D4)
│     ├── basis-D6  Stop metrics/google taxing bare `import my`      (defer imports; doc plugin tax)
│     ├── basis-D7  Fix wrong-extra ImportError message ([google])   (1 decorator; shared helper)
│     ├── basis-D8  mdformat-front-matters → core (or activate exts) (fixes silent corruption)
│     ├── basis-D9  Document the extras (README + docstrings)        (no code)
│     ├── basis-D10 ⚠ numpy decision — benchmark-gated REPLACE/KEEP  (only real rabbit-hole)
│     └── basis-D11 Correct README "32 deps / ~250MB" → measured     (folds into X1)
│
├── basis-C  Correctness & Security Bugs   (each with a reproduced repro → regression test)
│     ├── basis-C1  ⭐ shlex/argv fix print_in_color RCE
│     ├── basis-C2  ⭐ shlex.quote/shell=False in Command.execute
│     ├── basis-C3  ⭐ Lock the global MyType/Match caches (thread-safety)
│     ├── basis-C4  ⭐ Fence-aware Markdown header scanning
│     ├── basis-C5  Year regex: open-ended bound + century pivot + md_url paren balance
│     ├── basis-C6  Move Markdown notes/frontmatter inside a Jinja block
│     ├── basis-C7  Environment: import-time snapshot + set() cache-clear bug
│     ├── basis-C8  SystemUtils logging cluster (root logger, **kwargs, map())
│     ├── basis-C9  cast list/element coercion in the "wraps" fallback
│     ├── basis-C10 Annotated[...] cast target (fall back to .main)
│     ├── basis-C11 MyEnum.write() empty-string value
│     ├── basis-C12 Guard cyclic-data recursion (typed decline)
│     ├── basis-C13 NestedCache child config propagation
│     ├── basis-C14 SyntaxUtils.nested_replace tuple contract
│     ├── basis-C15 PickleCache atomic write + trust-boundary doc
│     ├── basis-C16 MetricUtils setup_metrics rm -rf + sub-ms drop
│     └── basis-C17 RegexStore timeout bypass via raw-pattern accessors
│
├── basis-P  Packaging & Namespace
│     ├── basis-P1  ⭐ Un-claim top-level `data` (nest under my/, or __init__+drop namespace)
│     ├── basis-P2  Un-ship test fixtures (importas.yaml, snapshots) from the wheel
│     └── basis-P3  Delete or wheel-exclude dead Idx.py / IdxSpec.py
│
├── basis-T  Test-Suite Hardening
│     ├── basis-T1  ⭐ Real ReDoS/timeout + pair_list cache + console-script smoke tests
│     ├── basis-T2  Make conftest hermetic (no ~/local/logs write at import)
│     ├── basis-T3  Fix Environment singleton leak in test_Environment
│     └── basis-T4  Remove/repair false Predicate.serialize xfail comment
│
├── basis-X  Docs & README
│     ├── basis-X1  ⭐ README rewrite (install, quickstart, py-version, my/base link, Modules)
│     ├── basis-X2  CHANGELOG 0.8.2 entry + Unreleased section
│     ├── basis-X3  ⭐ Make `task docs` build (intersphinx) + provision RTD
│     ├── basis-X4  Restore PyPI badges; leave RTD badge until provisioned
│     ├── basis-X5  Typist :inherited-members: + Platform/Filesystem pages
│     └── basis-X6  Regenerate dependency-tree docstring from real import graph
│
├── basis-M  CI / Release Machinery
│     ├── basis-M1  ⭐⚠ Verify/revoke classic PyPI token (operator)
│     ├── basis-M2  Add green-main pipeline-status gate to Publish (or accept+document)
│     ├── basis-M3  Purge dist/ + clean-build step
│     ├── basis-M4  tag == pyproject version assertion in Publish before_script
│     ├── basis-M5  Bump version off 0.8.3; adopt post-tag -dev bump
│     ├── basis-M6  Delete dead .pre-commit-config.yaml; wire or remove yamlfmt/taplo/plumber
│     ├── basis-M7  Re-enable or retire the exclude-newer comment
│     ├── basis-M8  AST_ENABLE_MR_PIPELINES for pre-merge secret detection
│     └── basis-M9  Scheduled base-image rebuild
│
└── basis-A  API Surface & Naming  (mostly pre-1.0-stability hygiene)
      ├── basis-A1  ⭐ De-shadow my.utils (drop `utils` from facade) + regression test
      ├── basis-A2  ⚠ Rein in alias sprawl (pick canonical; stop advertising the rest)
      ├── basis-A3  Rename/withhold underscore names (_Func/_Map/_Vec/_Struct) from __all__
      ├── basis-A4  Document my.text/my.type shims + set a removal version
      └── basis-A5  Add MetricUtils to my.__all__ + facade-completeness regression test
```

______________________________________________________________________

## 4. Worked example — the Dependency & Import Slice (`basis-D`)

The maintainer's stated problem: *"how to offer useful code with minimal bloat from unused dependencies when needed."* Here is the full slice, from measured diagnosis to concrete design to ordered execution — the template every other slice follows.

### 4.1 The measured problem

| Bookend                                     | Distributions | site-packages | `import my` wall | Notes           |
| ------------------------------------------- | ------------- | ------------- | ---------------- | --------------- |
| **Core-only** (bare `pip install my-basis`) | 25            | 83 MB         | ~186 ms          | the floor       |
| **All-extras runtime**                      | 91            | 295 MB        | —                | non-dev closure |
| **As-shipped dev venv**                     | 142           | 381 MB        | ~435 ms          | the ceiling     |

README claims "32 dependencies / ~250 MB" — **refuted at both ends** (25/83 core, 91/295 all-extras).
Where the import time actually goes (dev venv, `-X importtime`): **~34%** to a `logfire`→OpenTelemetry cascade triggered by pydantic's plugin loader the instant basis defines its first `BaseModel`, and **~37%** to the eager-but-guarded `MetricUtils` (pandas) and `GoogleSheet` (googleapiclient) subtrees — **two-thirds of import cost is optional features nobody requested.**

Three of the fourteen *core* dependencies are imported **nowhere**: `identify`, `toolz`, `tqdm` (verified — `identify` unused since the initial commit).
Meanwhile `numpy` (60 MB) is genuine (real array math in `Buffer`, not decorative — cleared), and the crucial insight from the consumer survey: **only 27 of the facade's 90 exported names are used anywhere across all 11 consumers** — 63 are dead facade weight, the safest subtraction target in the whole review.

### 4.2 The design — minimal-core, correct-when-needed

The principle: **core stays eager and cheap; everything heavy or optional is deferred to first use, with an actionable error when its extra is absent.** The codebase already contains the right pattern twice (`aiohttp` via a `sys.modules` check, `pyratatui` function-local + `TYPE_CHECKING`) — this slice makes `apis`/`files`/`metrics`/`google` consistent with basis's own better precedent.

**Target core (14 → 11 declared; 8 eager, 3 lazy):**

```toml
dependencies = [
  "more-itertools>=10.7.0",         # KEEP  — 60 sites, woven throughout
  "pydantic>=2.11.7",               # KEEP  — foundational
  "regex>=2024.4.28",               # KEEP  — VERSION1/(?R)/timeout=, stdlib re can't
  "srsly>=2.5.1",                   # KEEP  — bundles json+yaml+pickle
  "tomli-w>=1.2.0",                 # KEEP  — tiny, real stdlib gap
  "python-dotenv>=1.2.2",           # RENAMED from the `dotenv` trampoline; import unchanged
  "mdformat>=0.7.22",
  "mdformat-front-matters>=2.0.0",  # MOVED from `myst` — core render() corrupts frontmatter without it
  "jinja2>=3.1.6",                  # declared, import deferred into get_template()
  "python-dateutil>=2.9.0.post0",   # declared, import deferred into the fallback branch
  "unidecode>=1.4.0",               # declared, import deferred into clean_string()
]
# numpy — basis-D10, benchmark-gated (see below)
# identify, toolz, tqdm — DROPPED (zero usage, verified)
```

**Lazy facade** (`basis-D4`/`D5`) — `apis` and `files` are the only *leaf* subpackages (nothing under `my/` imports them), so they alone can defer without breaking the internal graph.
The documented `from my import ty, MyType` contract is untouched (both are in the eager set):

```python
# my/__init__.py sketch
from typing import TYPE_CHECKING
# ... eager: infra.types, utils (NOT `utils` — that's the A1 shadow fix), caches, typing, types, regex ...

if TYPE_CHECKING:                       # checkers/autocomplete still see the names
    from .apis import GoogleSheet, Environment, ENV, env, Filesystem, PATHS, FS, fs
    from .files import Markdown

_LAZY = {'GoogleSheet','Environment','ENV','env','Filesystem','PATHS','FS','fs','Markdown'}

def __getattr__(name):
    if name in _LAZY:
        from . import apis, files
        return getattr(apis, name, None) or getattr(files, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
```

This alone removes the ancestor-directory `.env` walk, the `os.environ` snapshot, the `platform-conventions.yaml` read, the `data` namespace import, and the Jinja `PackageLoader` stat from every `import my` that doesn't touch `apis`/`files`.
**Honest limits:** `from my import env` still pays the full cost at that import; `from my import *` and `hasattr(my,'env')` defeat laziness — a one-line docs note, not a blocker.

**Actionable extras errors** (`basis-D7`) — collapse the two copy-pasted guards into one parameterized decorator so the message names the *right* extra:

```python
raise ImportError(f'{fn.__qualname__}() requires the optional [{extra}] extra: '
                  f'pip install my-basis[{extra}]')   # → "[google]", not "[metrics]"
```

**`py.typed`** (`basis-D3`) — `touch my/py.typed`, confirm the `uv_build` glob ships it.
Near-pure bug fix; makes the `Typing :: Typed` classifier true and every consumer's checker actually read basis's types.

**mdformat extension activation** (`basis-D8`) — either move `mdformat-front-matters` to core, or build the extension set at the call site from what's importable (`{'front_matters','myst'} & set(mdformat.plugins.PARSER_EXTENSIONS)`) so `Markdown.render()` stops silently destroying frontmatter and the `[myst]` extra stops being a no-op.

### 4.3 Execution order (dependencies first, cheapest-safe first)

1. **`basis-D1`, `basis-D2`, `basis-D3`, `basis-D11`** — zero-risk, minutes each: drop 3 dead deps, repin dotenv, add `py.typed`, correct the README number.
   No consumer breaks (survey-confirmed).
2. **`basis-D7`, `basis-D8`, `basis-D9`** — fix the wrong-extra message, activate mdformat extensions, document extras.
   Small, local, high-UX-payoff.
3. **`basis-D4` + `basis-D5` + `basis-D6`** — the lazy-facade change, landed together (they're one edit to `my/__init__.py` + `apis`/`__init__`).
   Blast radius: the survey found deep-path importers (`corpus`, wikiparse family via `my.infra.constants`) bypass the facade entirely and are unaffected; `from my import ty, MyType` is unaffected.
   Ship with a smoke test across the real consumers' import patterns.
4. **`basis-D10`** ⚠ — the only rabbit-hole: numpy is baked into a pydantic field annotation (`Buffer.fences`), so it *cannot* be made lazy — the choice is KEEP (60 MB) or REPLACE with plain Python.
   REPLACE touches flagship hot-path code and rests on the unverified assumption that per-document fence counts are small.
   **Gate on a large-document benchmark first**; do not attempt blind.

### 4.4 Why this is the right template

Notice the shape, which every other slice reuses: **measure before cutting** (the 27-of-90, the import-time attribution), **lean on the codebase's own best precedent** rather than importing a foreign pattern, **cost every change against the real consumer graph** (so "drop tqdm" is safe and "de-shadow utils" breaks exactly one known site), and **separate the mechanical wins from the one judgement call** so the slice delivers value immediately and blocks only where a human decision is genuinely required.
That is the posture for `basis-C` through `basis-A` as well.

______________________________________________________________________

## 5. Recommended sequencing across slices

- **First, in parallel (all mechanical, no cross-conflict):** `basis-D1/D2/D3/D11`, `basis-X1/X2/X4`, `basis-M3/M5`, `basis-P3`, `basis-T4`.
  A day of low-risk cleanups that erase the most visible "unfinished" signals (false PyPI claim, broken quickstart, missing py.typed, dead deps, stale dist/).
- **Then the security/correctness core:** `basis-C1/C2/C3/C4/C5` (the reproduced RCE/crash/corruption set), each landing with the repro turned into a regression test — this is what actually moves the needle from "green suite" to "trustworthy suite" (`basis-T1`).
- **Then the structural changes:** `basis-D4-6` (lazy facade), `basis-P1/P2` (data namespace), `basis-A1` (de-shadow) — larger edits, each with a consumer smoke-test.
- **Operator-gated, do early because it's a phone call:** `basis-M1` (PyPI token verify/revoke) and `basis-M2` (accept-and-document vs enforce the green-main convention).
- **Last, pre-1.0 API stability:** `basis-A2/A3/A4` — the naming and shim decisions that a 1.0 compatibility promise locks forever, so make them deliberately and just before the tag.

______________________________________________________________________

## Problem space

- **basis-1.0** ⭐ *the release campaign; sign-off gated on the blocker set clearing*
  - **basis-D** *worked example — dependency slice; mostly mechanical, one benchmark gate (D10)*
    - *D1-3, D11 shippable today, zero blast radius → start here*
  - **basis-C** *the reproduced bug set; C1-C4 are the real sign-off movers (RCE ×2, thread crash, doc corruption)*
  - **basis-P** *namespace/packaging; P1 (un-claim `data`) is breaking-if-deferred → decide before 1.0*
  - **basis-T** *turn repros into regression tests; the suite is green but under-guards the 0.8.3 release*
  - **basis-X** *docs; X1 + X3 are the visible-polish keystones (README truth, buildable docs)*
  - **basis-M** *machinery; M1 is operator-gated (PyPI token) — the one true external dependency*
  - **basis-A** *API/naming; A1 (de-shadow) is a bug, A2 (aliases) is the pre-1.0 judgement call*
- *True terminus:* none of the seven slices block each other structurally — `basis-D` is sequenced first only because it's the maintainer's named priority and its early tasks are the safest wins.
  The real gate is **basis-M1** (a human PyPI-settings check) + the **basis-C1-C4** fixes; everything else is parallelizable.
