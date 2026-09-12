<!-- readme-header:begin -->

<div align="center">

<img src="assets/logo_512.png" alt="myBasis logo" width="180">

# myBasis: _Ergonomic Python Utilities_

<p align="center">
  <a href="https://gitlab.com/doering-ai/libs/basis/-/pipelines"><img src="https://img.shields.io/gitlab/pipeline-status/doering-ai%2Flibs/basis" alt="pipeline status"></a> <a href="https://gitlab.com/doering-ai/libs/basis/-/blob/main/LICENSE"><img src="https://img.shields.io/gitlab/license/doering-ai%2Flibs/basis" alt="license"></a> <a href="https://pypi.org/project/my-basis/"><img src="https://img.shields.io/pypi/v/my-basis" alt="PyPI version"></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/my-basis/"><img src="https://img.shields.io/pypi/pyversions/my-basis" alt="PyPI - Python Version"></a> <a href="https://pypi.org/project/my-basis/"><img src="https://img.shields.io/pypi/wheel/my-basis" alt="PyPI - Wheel"></a> <a href="https://pypi.org/project/my-basis/"><img src="https://img.shields.io/pypi/types/my-basis" alt="PyPI - Types"></a> <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=precommit" alt="pre-commit"> <a href="https://github.com/facebook/pyrefly"><img src="https://img.shields.io/endpoint?url=https://pyrefly.org/badge.json" alt="pyrefly"></a> <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="ruff"></a>
</p>

</div>

<!-- readme-header:end -->

The myBasis utility package — imported as `my` — is a broad extension of the Python standard library centered on text processing, functional programming, and runtime type coercion.
The use cases are diverse enough to not enumerate them all here, but they all share a strong sense of discipline: all code is thoroughly typed, tested, and [documented](docs/index.md) following my best pass at best practices (it does get easier!).

I made this module to streamline some patterns that seemed both A) frequently-relevant and feasible to streamline.
The repo thus grew alongside my projects over time, a genesis which gives it the advantage of being in daily use by the original author in multiple examples right off the bat.

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

## Installation

<blockquote class="artificial-prose">

In an activated Python 3.13+ environment:

</blockquote>

```sh
uv pip install my-basis
# or:
python -m pip install my-basis
```

## A first example

<blockquote class="artificial-prose">

Start with `ty`: cast a value into a target type, check whether it already fits, or inspect the type itself.
Casting and checking are deliberately different operations.

</blockquote>

```python
from my import ty, MyType

ty.cast('42', int)                            # -> 42
ty.cast(['1', '2', '3'], list[int])           # -> [1, 2, 3]
ty.cast({'a': '1', 'b': '2'}, dict[str, int]) # -> {'a': 1, 'b': 2}

ty.check(42, int)      # -> True
ty.check('42', int)    # -> False
ty.match('hello', str | int)  # -> True

t = MyType(dict[str, int])
t.main    # -> <class 'dict'>
t.args    # child MyType nodes for str and int
t.root    # -> dict[str, int]
```

<blockquote class="artificial-prose">

`ty` is the shared `Typist` instance, combining `cast`, `check`, and `match`.
Use the [typing guide](my/typing/README.md) when the coercion rules themselves matter.

</blockquote>

## Find your corner

<blockquote class="artificial-prose">

Seven public subpackages cover the main jobs.
The root re-exports their public names, so `from my import ut, ty, Span, Markdown` is enough for the examples here.
The heavier `apis` and `files` branches load lazily.

</blockquote>

| Area                | Start here                                                                | Useful for                                                                          |
| ------------------- | ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Utilities           | [`ut`](my/utils/README.md)                                                | Partitioning iterables, transforming text, working with syntax and system resources |
| Runtime typing      | [`ty`, `MyType`, `AutocastModel`](my/typing/README.md)                    | Coercion, conformance checks, and inspecting annotations                            |
| Reusable types      | [`Span`, `Buffer`, `Command`](my/types/README.md)                         | Intervals, mutable text, and reusable shell invocations                             |
| Regular expressions | [`RegexStore`, `MatchData`](my/regex/README.md)                           | Composing named patterns and inspecting matches                                     |
| Caches              | [`Cache`, `NestedCache`, `FileCache`, `PickleCache`](my/caches/README.md) | In-memory, hierarchical, disk-backed, and expiring storage                          |
| Interfaces          | [`env`, `fs`, `GoogleSheet`](my/apis/README.md)                           | Typed environment access, named paths, and optional spreadsheet integration         |
| File formats        | [`Markdown`](my/files/README.md)                                          | Parsing, walking, and editing a document tree                                       |

## A short tour

### Utilities

<blockquote class="artificial-prose">

`ut` collects the utility families into one namespace.
You can also import a family directly—`IterUtils` and `iter_utils`, for example, name the same class.
One detail worth noticing below: `find` returns an index, not the matching value.

</blockquote>

```python
from my import ut

ut.partition([1, 2, 3, 4], lambda x: x % 2 == 0)  # -> ([1, 3], [2, 4])
ut.condense(['a', None, '', 'b', 0])              # -> ['a', 'b']
ut.find([3, 8, 2], lambda x: x > 5)               # -> 1
```

### Runtime typing

<blockquote class="artificial-prose">

[`AutocastModel`](docs/typing.AutocastModel.md) applies the casting rules during Pydantic validation.
It's useful when incoming values are close to the shape you need, including a scalar where your model expects a list.
Use it where that permissiveness is intended.

</blockquote>

```python
from my import AutocastModel

class Settings(AutocastModel):
    port: int = 0
    debug: bool = False
    tags: list[str] = []

s = Settings(port='8080', debug='true', tags='solo')
(s.port, s.debug, s.tags)  # -> (8080, True, ['solo'])
```

### Reusable types

<blockquote class="artificial-prose">

The types branch gives recurring concepts their own objects.
[`Span`](docs/types.Span.md), for instance, represents a half-open interval and handles its length and overlap checks.
The shared type vocabulary also pairs annotation aliases such as `Atom` with runtime tuples such as `Atoms`.

</blockquote>

```python
from my import Span

a, b = Span(3, 9), Span(8, 12)
a.delta          # -> 6
a.intersects(b)  # -> True
```

### Regular expressions

<blockquote class="artificial-prose">

[`RegexStore`](docs/regex.RegexStore.md) gives patterns names you can compose and reuse.
[`MatchData`](docs/regex.MatchData.md) keeps repeated groups accessible, and `COMMON_RGXS` supplies a collection of ready-made patterns.
The [meta layer](my/regex/meta/README.md) is there when you need to inspect the expression itself.

</blockquote>

```python
from my import RegexStore, COMMON_RGXS

COMMON_RGXS.findall('url', 'visit https://example.com or www.foo.dev')
# -> [MatchData("https://example.com" -> {'url': ['example.com']}),
#     MatchData("www.foo.dev" -> {'url': ['foo.dev']})]

store = RegexStore()
store.define('greeting', r'hello (?P<name>\w+)')
print(store.search('greeting', 'hello world'))  # -> name: world
```

### Caches

<blockquote class="artificial-prose">

Choose a cache by its storage pattern: bounded memory, nested levels, memory over disk, or pickle-backed persistence with expiry.
The simplest case is a [`Cache`](docs/caches.Cache.md).
If you use `PickleCache`, load only data you trust—unpickling can execute code.

</blockquote>

```python
from my import Cache

cache = Cache(maxsize=256)
cache['answer'] = 42
cache['answer']  # -> 42
```

### Interfaces

<blockquote class="artificial-prose">

`env` snapshots environment variables when it first loads; `fs` provides a named path registry.
Set demonstration variables before importing `env` (or use a fresh process if you've already loaded it).
`GoogleSheet` adds spreadsheet access through the optional `google` extra.

</blockquote>

```python
import os
os.environ['DEMO_FLAG'] = 'true'

from my import env

env.get('DEMO_FLAG')   # -> 'true'
env.flag('DEMO_FLAG')  # -> 1 (0 when unset)
```

### File formats

<blockquote class="artificial-prose">

[`Markdown`](docs/files.Markdown.md) parses a document into a hierarchy of sections while respecting fenced code.
You can walk the nodes, edit them, and render the result.

</blockquote>

```python
from my import Markdown

root = Markdown.parse('# Title\n\nIntro prose\n\n## Section A\n\nBody\n')[0]
[str(node).splitlines()[0] for node in root.walk()]  # -> ['# Title', '## Section A']
```

## Optional integrations

<blockquote class="artificial-prose">

Install extras only for the integrations you use: `uv pip install "my-basis[metrics]"` or `python -m pip install "my-basis[metrics]"`, for example.
In a uv-managed project, the equivalent dependency declaration is `uv add "my-basis[metrics]"`.

</blockquote>

| Extra      | Adds                                                                                        |
| ---------- | ------------------------------------------------------------------------------------------- |
| `metrics`  | Logfire/OpenTelemetry logging, counters, and instrumentation helpers through `MetricUtils`  |
| `google`   | `GoogleSheet` access, OAuth support, and pandas `DataFrame` conversion                      |
| `myst`     | MyST syntax support in `Markdown.render()`'s formatting pass                                |
| `terminal` | The pyratatui-backed examples under [`my/scripts/tuitorii/`](my/scripts/tuitorii/README.md) |
| `aiohttp`  | An HTTP-client convenience dependency; it does not unlock a separate API by itself          |

## Why this library

Its breadth is somewhat unusual: any given application will probably use a small subset of the contents, so it shines where dependency purity isn't paramount — personal projects, local dev scripts, offline data processing, prototypes, and the project you're working on right now are the ideal usecases.
As a rough sense of scale: a bare `pip install my-basis` pulls a couple dozen distributions (on the order of ~80 MB unpacked), and turning on every optional extra can push a full environment past ~290 MB because of heavy common dependencies like `pandas`, `numpy`, and various pieces of rubble amongst the ruins Google's Python SDK ecosystem.
I do still kinda recommend that for personal scripts/admin/env/dev projects, where having the ability to easily work with google sheets, cast types, or performantly write all kinds of filetypes is worth more than some disk space.

The 1.0 release has been cut, beyond which I intend to enforce strict semver; don't expect breaking changes any time in the foreseeable future.
If you're like me (i.e. have ADHD?), this library will spark the most joy when you are vaguely aware of its contents and know it's at your fingertips at any time while coding; not only can it save you a bunch of time writing functions, but the prospect of attempting functions with it in hand is so much more approachable that a lot more ends up getting done.

If that makes sense?
I guess I'm really trying to sell you the promise of **bolder, quicker software engineering.**

## Refactor an existing repository

<blockquote class="artificial-prose">

The package includes a read-only source scanner and the `adopt-my-basis` agent skill.
From a Python repository you want to assess:

</blockquote>

```sh
uvx --from my-basis my-basis-adopt skill path
uvx --from my-basis my-basis-adopt skill export .agents/skills/adopt-my-basis
uvx --from my-basis my-basis-adopt prepare .
```

<blockquote class="artificial-prose">

Give the resulting `intake.json` path to your agent.
The scanner inventories files, dependencies, Python compatibility, candidate checks, and regex structure without importing the target package or editing its source; `prepare` writes its intake artifacts.
The agent can then assess a proposal and produce a MyST, HTML, or Typst/PDF report.
A justified decline or no-op is a valid result.

`skill path` locates the packaged instructions; `skill export` copies them when your agent needs a local catalogue entry.
See the [full workflow](my/skills/adopt-my-basis/SKILL.md) and [RegexStore adoption guide](my/skills/adopt-my-basis/references/regexstore.md).

</blockquote>

## Documentation and development

<blockquote class="artificial-prose">

The [Sphinx/MyST documentation](docs/index.md) provides class references and examples.
From a checkout, install the development dependencies and build it with:

</blockquote>

```sh
task sync
task docs
```

<blockquote class="artificial-prose">

Use the [test guide](tests/README.md) for the suite and its conventions.
Python 3.13 is the current minimum; the source uses modern typing syntax throughout.
Pydantic is a core dependency even when your own code does not use Pydantic models.
The separate [Typst package](typst/README.md) has its own installation path and is not part of the Python wheel.

GitLab is the development forge; the GitHub repository is a read-only source mirror.
Report issues and propose changes at [the GitLab project](https://gitlab.com/doering-ai/libs/basis).

</blockquote>

## Contributing

The project was built over the course of 2025 for its author's own use, so it's definitely opinionated — influenced by a weathered respect for polymorphism, an addiction to ergonomic code in the Don-Norman sense, and a reliance on symbolic, deterministic devtools (heavy typing, even at runtime).
If any of that resonates: get in touch, or open an issue or merge request on GitLab.

Licensed under [MPL-2.0](LICENSE).
