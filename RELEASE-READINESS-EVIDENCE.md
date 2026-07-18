---
title: myBasis 1.0 Release-Readiness — Evidence Appendix
status: draft
date: 2026-07-18
companion: RELEASE-READINESS.md
note: Durable proof layer — repros, file:line, and measured tables behind every finding.
---

# myBasis 1.0 Release-Readiness — Evidence Appendix

Companion to [`RELEASE-READINESS.md`](RELEASE-READINESS.md).
That file carries the verdict and the task tree; **this file preserves the proofs** — the reproductions, exact `file:line` anchors, and the empirical tables produced by the 10-agent fan-out — so a maintainer can sign off from evidence rather than assertion after the session's scratch is gone.

**Verification legend:** `[V]` re-run directly by the orchestrator against the working tree; `[S]` reproduced by the subagent (snippet + observed output recorded below); `[src]` confirmed by reading source.
Blockers carry at least `[V]` or `[src]`.

______________________________________________________________________

## A. Measured tables (the irreplaceable empirical artifacts)

### A.1 Import cost & closure size

| Bookend                                       | Distributions | site-packages | `import my` wall (perf_counter ×3) | `-X importtime` cumulative |
| --------------------------------------------- | ------------- | ------------- | ---------------------------------- | -------------------------- |
| Core-only (`pip install my-basis`, no extras) | 25            | 83.0 MB       | 176 / 179 / 202 ms                 | 178 ms                     |
| All-extras runtime (`--no-dev --all-extras`)  | 91            | 295.3 MB      | —                                  | —                          |
| As-shipped dev venv (all extras + dev groups) | 142           | 381.3 MB      | 411 / 454 / 440 ms                 | 672 ms                     |

- **Import-time attribution (dev venv):** `logfire`→OpenTelemetry cascade via pydantic's plugin loader ≈ **34%** (~228 ms), triggered the instant basis defines its first `BaseModel` (`my/infra/constants.py:23` `class InfraPaths`).
  `MetricUtils` (pandas) subtree = 137,599 µs vs 784 µs absent (~176×); `GoogleSheet` (googleapiclient) subtree = 112,436 µs vs 650 µs absent (~173×) — together ≈ **37%**.
  `[S]`
- **README "32 dependencies / ~250 MB" — refuted at both ends** (25/83 core, 91/295 all-extras).
  `[V]`

### A.2 Per-core-dependency necessity (14 declared)

| Dep             | Sites in `my/`                    | Verdict               | Note                                                                                                |
| --------------- | --------------------------------- | --------------------- | --------------------------------------------------------------------------------------------------- |
| pydantic        | ~40 files                         | KEEP-CORE             | foundational                                                                                        |
| regex           | ~29 files                         | KEEP-CORE             | VERSION1 / `(?R)` / `timeout=`; stdlib `re` can't                                                   |
| more-itertools  | 60 sites / 22 files               | KEEP-CORE             | woven throughout                                                                                    |
| srsly           | 11 sites                          | KEEP-CORE             | json+yaml+pickle bundle; 5.7 MB (heavyish)                                                          |
| tomli-w         | 1                                 | KEEP-CORE             | tiny, real stdlib gap (write half of `tomllib`)                                                     |
| numpy           | 9 sites, **1 file** (`Buffer.py`) | KEEP or ⚠REPLACE      | 60 MB; genuine array math (**cleared** — not decorative); can't be lazy (pydantic field annotation) |
| jinja2          | 1 call + eager `Environment()`    | MAKE-LAZY             | real `extends`/`super()`/recursive-loop use                                                         |
| mdformat        | 1 (`Markdown.py:689`)             | KEEP-CORE + fix split | broken without its plugin (see C-D8)                                                                |
| dotenv          | 1 (`Environment.py:13`)           | REPIN → python-dotenv | 1.9 KB trampoline; `uv.lock:542-550` shows it only requires `python-dotenv`                         |
| python-dateutil | 1 (`cast.py:698`)                 | MAKE-LAZY             | last-resort fallback after stdlib `fromisoformat`                                                   |
| unidecode       | 1 (`TextUtils.py:267`)            | MAKE-LAZY             | powers `clean_string`, called only by its own test                                                  |
| **identify**    | **0**                             | **DROP**              | unused since the initial commit `[V]`                                                               |
| **toolz**       | **0**                             | **DROP**              | superseded by more-itertools `[V]`                                                                  |
| **tqdm**        | **0**                             | **DROP**              | zero occurrences anywhere `[V]`                                                                     |

### A.3 site-packages weight (top entries, `du` over dev venv, 381 MB total)

| Entry                     | Size     | Class                       |
| ------------------------- | -------- | --------------------------- |
| googleapiclient           | 96.6 MB  | extra (google)              |
| pandas                    | 49.2 MB  | extra (metrics+google)      |
| numpy + numpy.libs        | 58.4 MB  | **core**                    |
| cryptography              | 14.6 MB  | extra (google-auth)         |
| srsly                     | 5.7 MB   | **core**                    |
| pydantic_core + pydantic  | 8.1 MB   | **core**                    |
| regex                     | 3.1 MB   | **core**                    |
| opentelemetry (11 dists)  | 3.8 MB   | extra (metrics)             |
| logfire / rich / pygments | ~11.6 MB | extra (metrics, transitive) |

Category totals: **extra 212.3 MB · dev 84.6 MB · core 83.0 MB.**

### A.4 RegexStore timeout-coverage (CHANGELOG 0.8.3 claim: "enforce timeouts across RegexStore matchers")

**True for the store's own public matchers; bypassed by its own public raw-pattern accessors.** `[S]`

| Call site                                                                                        | `timeout=`?                                                                       |
| ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `RegexStore._autoparse` → `.match/.fullmatch/.search` (`RegexStore.py:511`)                      | **YES** (verified raises `TimeoutError`)                                          |
| `RegexStore.finditer` str-path (`RegexStore.py:988`)                                             | **YES**                                                                           |
| Buffer hot iterators (`Buffer.py:467,825,948`)                                                   | **YES** (`REGEX_TIMEOUT=10.0`)                                                    |
| `Environment.RGXS.*` (`Environment.py:205,245,268`)                                              | **YES** (via store)                                                               |
| **`Filesystem._check_for_project_root`** (`Filesystem.py:166,168`)                               | **NO** — raw `.search()` on `RGXS['leaf']`, hangs on evil pattern (killed at 5 s) |
| `ParseData.apply_dict_parser` (`ParseData.py:93`)                                                | NO — inside the store's own pipeline                                              |
| `TextUtils.replace/split_into` (`TextUtils.py:50,71`)                                            | NO — caller-supplied pattern **and** text                                         |
| `SystemUtils` yaml/pathy (`SystemUtils.py:607,645`), `FileCache.search` (`FileCache.py:469,481`) | NO — over full file contents / caller patterns                                    |

Outside `RegexStore`/`Buffer` there is **no `REGEX_TIMEOUT` concept at all** — it's a store-only mechanism, not package-wide.

### A.5 Facade usage across 11 ecosystem consumers (blast-radius survey)

- **Only 27 of the facade's 90 `__all__` names are imported anywhere; 63 are dead facade weight.** `[S]`
- Top symbols: `ut` (140), `Uid` (106), `typist` (78), `env` (52), `RegexStore` (48), `Buffer` (41), `UniqueId` (24), `Span` (22), `MyEnum`/`MatchData` (18), `FileCache` (17).
- Consumer footprint: `ai` (176 sites, mostly `Uid`), wikiparse family ×3 (~95 sites, deep-path `my.infra.constants`), `arch` (24), `means` (21), `corpus` (11), `admin` (6), `model` (7).
- **Change-cost map:** de-shadow `my.utils` → breaks **1** site (`means/cli/report.py:29`); delete `my.text`/`my.type` shims → **0** breaks; un-ship top-level `data` → **0** downstream breaks; drop tqdm/numpy from core → **0** facade breaks; lazy facade → **0** functional breaks (deep-path importers bypass it either way).
- **Latent bug surfaced:** `corpus` and `arch` call `GoogleSheet()` **without** the `google` extra — silently running against `MagicMock` (sync path is a no-op today).
  Hardening the extras error would surface this loudly.

### A.6 Extras install sizes (fresh venv per extra, measured pre-import)

| Install      | site-packages | Δ vs bare | Effect                                                                        |
| ------------ | ------------- | --------- | ----------------------------------------------------------------------------- |
| bare         | 79 MB         | —         | imports clean, all 7 subpackages OK                                           |
| `[google]`   | 244 MB        | +165 MB   | `GoogleSheet.INSTALLED` → True                                                |
| `[metrics]`  | 137 MB        | +58 MB    | `METRICS_INSTALLED` → True                                                    |
| `[terminal]` | 92 MB         | +13 MB    | pyratatui (correctly lazy)                                                    |
| `[myst]`     | 82 MB         | +3 MB     | **no-op** — plugins register but `mdformat.text()` never passes `extensions=` |
| `[aiohttp]`  | 88 MB         | +9 MB     | **gates nothing** in `my`                                                     |

______________________________________________________________________

## B. Blocker & high-severity repros (verbatim)

### C1 — `SystemUtils.print_in_color()` shell injection (RCE) `[S]`

`my/utils/SystemUtils.py:260`:

```python
ret = sbp.run(f'zsh -c \'print -P "{text}"\'', capture_output=True, text=True, shell=True)
```

```python
evil = "x'; touch /tmp/.../INJECTED_MARKER; echo 'y"
SystemUtils.print_in_color(evil)     # -> marker file created: True
```

### C2 — `Command.execute()` shell injection (RCE) `[V]`

`my/types/Command.py`: `_shell_quote` (line 24, double-quote-only) + `shell=True` (lines 198, 216).

```text
assembled: echo --foo "$(touch .../C2_MARKER && echo INJECTED)"
marker created: True          # $(...) command substitution executed
```

### C3 — global type caches, structural data race `[src]` + `[S]`

`my/typing/MyType.py:182` `PARSE_CACHE: ClassVar[Cache] = Cache()`; write at `:344`.
`my/caches/Cache.py`:

```python
def __setitem__(self, key, value):
    if key not in self.data and len(self.data) >= self.maxsize:
        self.prune(self.bucket_size)
    self.data[key] = value
def prune(self, n):
    for key in mi.take(n, self.data.keys()):   # iterate keys()
        del self.data[key]                     # ...while deleting -> race
```

`grep Lock|threading my/caches/ my/typing/MyType.py` → **nothing** `[V]`.
Subagent 8-thread run raised `KeyError: -8292946722296174967` in `Cache.prune`.
Orchestrator reruns didn't hit the window (narrow under the GIL; race is structural regardless).
Fix: lock the cache mutators, or document not-thread-safe.

### C4 — `Markdown.parse()` corrupts docs with `#`-comment code fences `[V]`

`my/files/Markdown.py:44,56` (`marks=r'(?m)^#{1,6} +'`, no fence tracking).

````text
input:  # Title / ```python / # a comment / def f(): pass / ``` / ## Section Two
parse:  top-level nodes: 2
        title: 'Title'
        title: 'a comment'      # fabricated from the code comment; ## Section Two misnested under it
````

### C5 — `common_rgxs.year` hardcodes 2026 upper bound `[V]`

`my/regex/common_rgxs.py:95-98` (`...|202[0-6]|...`).

```text
C.search('year','2026') -> {'year': '2026'}
C.search('year','2027') -> {}          # < 6 months from 2026-07-18
```

Also (`[S]`): apostrophe-year `"'99"` → `'2099'` (no century pivot); `md_url` truncates targets with inner `)` (`[link](.../(parens)/path)` → target `.../(parens`).

### C6 — `Markdown` `notes`/frontmatter is dead Jinja `[S]`

`data/templates/Markdown.md.jinja` emits frontmatter **outside** any `{% block %}` under `{% extends 'document.md.jinja' %}` → discarded by Jinja.

```python
Markdown.new(title='D', notes={'title':'D','tags':['a','b']}, prose='c').render(..., fix=False)
# -> '# D\nc'      (notes vanish, in every environment, regardless of mdformat plugins)
```

### C7 — `Environment` import-time snapshot + `set()` cache bug `[V]`+`[S]`

`my/apis/Environment.py:24-25` (`load_dotenv()`; `initial_env = dict(os.environ)` once at import).

```text
import my; os.environ['ZZTOP']='x'; my.env.get('ZZTOP')  -> ''   # snapshot is stale [V]
```

`set()` skips cache-clear for previously-unset keys (`if cur := self.get(key)` — `''` is falsy), so a key read once while unset stays `''` forever after `set()`.
`[S]`

### C8 — `SystemUtils` logging cluster `[S]`

`my/utils/SystemUtils.py`: `logger = logging.getLogger()` (line 67 → **root** logger); `def warn(cls, *args, kwargs)` (missing `**`, line ~483) → `TypeError` on `warn("msg")`; `log()` passes a live `map` object as msg → emits `<map object at 0x...>`.

### C9 — `ty.cast('3', list[int])` skips element coercion `[V]`

`my/typing/cast.py:760-761` "wraps" fallback returns the raw string.

```text
ty.cast('3', list[int]) -> ['3']   (elem type: str)   # list[int] silently holds a str
```

### D3 — `py.typed` absent, classifier claims `Typing :: Typed` `[V]`

`find my -name py.typed` → empty; also absent from the built wheel.
`pyproject.toml:20` lists the classifier.
Every consumer's mypy/pyright sees `Any`.

### D7 — `GoogleSheet` guard names the wrong extra `[V]`

`my/apis/GoogleSheet.py:108`:

```python
raise ImportError(f'`utils.{name}()` requires the optional `[metrics]` dependency.')
```

Wrong extra (`[google]`), nonsensical `utils.` prefix; no source of truth anywhere names `[google]`.

### D8 — mdformat/myst split corrupts frontmatter `[V]`

```text
mdformat.text(src)                                   -> frontmatter mangled into a heading/rule
mdformat.text(src, extensions={'front_matters','myst'}) -> round-trips intact
```

`Markdown.py:689` calls `mdformat.text(body)` with no `extensions=`; the plugin lives in the `[myst]` extra, not core.
Core-only `Markdown.render(fix=True)` (the default) silently corrupts.

### B6/B7 — README contradicts reality `[V]`

PyPI JSON API: `my-basis` 0.8.1/0.8.2/0.8.3 all live — README says "not yet published".
Quickstart `ty.cast('a,b,c', list[str])` → `['a,b,c']` (not `['a','b','c']`; deliberate MEMY-325 change).
Also: "Built for Python 3.12+" vs `requires-python >=3.13`; dead link `my/base/utils.py` (no `my/base/`); \~25 empty "Modules" headers.

______________________________________________________________________

## C. Medium/low findings — anchors (one line each; repros in the transcripts)

- **C10** `ty.cast('5', Annotated[int,...])` → `None` (`cast.py:500-519` read `.root` not `.main`).
  `[S]`
- **C11** `MyEnum.write()` returns lowercased name for `''`-valued members (`MyEnum.py:96` truthiness).
  `[S]`
- **C12** cyclic data → bare `RecursionError` (`MyType.typeof`).
  `[S]`
- **C13** `NestedCache` children ignore configured `max_size`/`bucket_size` (`NestedCache.py:83`).
  `[S]`
- **C14** `SyntaxUtils.nested_replace()` returns `True` on tuples it never mutates (`SyntaxUtils.py:170-173`).
  `[S]`
- **C15** `PickleCache.write()` non-atomic (no tmp+rename); `read()` = undocumented pickle trust boundary (`PickleCache.py:82-86`).
  `[S]`
- **C16** `MetricUtils.setup_metrics()` `rm -rf` without `shell=True` → `FileNotFoundError` always; sub-ms timings dropped (`MetricUtils.py:450,463`).
  `[S]`
- **A1** facade shadow: `import my.utils as u` → the `Utils` class; `hasattr(u,'iter_utils')` False (`pyproject.toml` calls this static-only — false).
  `[V]`
- **P3** `import my.types.Idx` / `IdxSpec` → `ModuleNotFoundError: No module named 'myBasis'`; both still shipped in the wheel.
  `[V]`
- **T1** 0.8.3 claims untested: no test fires `REGEX_TIMEOUT`, no `md_url` ReDoS regression, no `pair_list()` cache test; console-scripts at 0% coverage.
  `[S]`
- **T2** `tests/conftest.py:21-27` writes `~/local/logs` at import (non-hermetic).
  `[S]`
- **T4** `pyproject.toml:190` cites a `Predicate.serialize` xfail that doesn't exist (`grep xfail tests/` empty).
  `[S]`
- **P1** wheel ships top-level `data` (PEP 420 namespace, no `__init__.py`); co-installing PyPI's real `data==0.4` silently merges dirs; PyPI's `my==1.3.0` silently shadowed.
  `[S]`
- **P2** `data/snapshots/test_RegexStore.ambr` + `data/importas.yaml` are test-only, shipped to every consumer.
  `[V]`
- **X3** `task docs` fails: 607 nitpick warnings-as-errors, missing `intersphinx_mapping`; plain `sphinx-build` succeeds clean.
  `[S]`
- **X5** hosted `Typist` page omits `cast/check/match` (no `:inherited-members:`); no `Platform`/`Filesystem` pages.
  `[S]`
- **X6** `my/__init__.py` dependency-tree docstring omits `infra` and hides the real `apis→regex` edge (defeats its anti-circular purpose).
  `[S]`
- **M1** `Taskfile.dist.yaml pkg:publish` uses long-lived `PYPI_TOKEN` outside CI/OIDC — "trusted-publishing only" is false if any classic token exists (**operator must verify on PyPI**).
  `[S]`
- **M2** tag pipelines skip Evaluate/Test; `Publish PyPI` has `needs: []`; secret-detection absent on tag pipelines; `pypi` approval is self-approval (verified live via GitLab API).
  `[S]`
- **M5** `version = "0.8.3"` with 16 unreleased commits on `main` (incl. a feature) → local build mislabels.
  `[V]`
- **M6** `.pre-commit-config.yaml` dead (prek.toml wins by precedence); `.yamlfmt`/`.taplo`/`.plumber` wired to nothing; `.plumber.yaml`'s own DinD rule already violated.
  `[S]`
- **M7** `exclude-newer` labeled "critical cybersafety measure; do not remove" but commented out/inactive.
  `[V]`
- **X2** CHANGELOG jumps 0.8.3 → 0.8.1 (0.8.2 shipped to PyPI, no entry); no Unreleased section.
  `[V]`

______________________________________________________________________

## D. Confirmed-fine (attacked and survived)

So the maintainer knows what was tested and held: `md_url` possessive-quantifier ReDoS fix (cubic→flat, timed); `Markdown.walk()` `-1` unlimited-depth fix (all boundary depths correct); `RegexStore` public matcher timeout enforcement (real `TimeoutError` at the deadline); nested-generic casts on well-formed input (`dict[str, list[int]]`, 5-deep nesting); union declaration-order tie-break; cache eviction/LRU/TTL round-trips (well tested); `MyType` `Annotated`/`Optional`/`Union` parsing; self-referential *type aliases* (only cyclic *data* crashes); no bare `except:` in the typing/types/infra layers; `AutocastModel` uses current pydantic-v2 APIs; numpy usage genuine; `project.scripts` entry points import clean; `uv.lock` in sync, no git/URL deps; protected tags/branches/environment configured correctly (verified live).
