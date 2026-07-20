![logo](assets/logo_512.png)

# myBasis: _Ergonomic Python Utilities_

> **Status:** Pre-launch — under active development.
> APIs may change before 1.0.

![Pipeline Status](https://img.shields.io/gitlab/pipeline-status/doering-ai/libs/basis?branch=main) ![Test Coverage](https://img.shields.io/gitlab/pipeline-coverage/doering-ai/libs/basis?branch=main) [![License](https://img.shields.io/gitlab/license/doering-ai/libs/basis)](/LICENSE)

[![PyPI Version](https://img.shields.io/pypi/v/my-basis)](https://pypi.org/project/my-basis) ![Python Version](https://img.shields.io/pypi/pyversions/my-basis) [![PyPI Wheel](https://img.shields.io/pypi/wheel/my-basis)](https://pypi.org/project/my-basis)

<!-- Not live yet -- restore once provisioned:
[![Documentation](https://app.readthedocs.org/projects/my-basis/badge)](https://my-basis.readthedocs.io)   ReadTheDocs -- not yet provisioned
[![PyPI Types](https://img.shields.io/pypi/types/my-basis)](https://pypi.org/project/my-basis)   accurate once the py.typed release ships
-->

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit) [![pyrefly](https://img.shields.io/endpoint?url=https://pyrefly.org/badge.json)](https://github.com/facebook/pyrefly) [![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

The myBasis Python package contains a variety of utilities generally centered around the topics of text processing, functional programming, and runtime type coercion.
This broad scope is somewhat unusual, as any given application will likely only need a small subset of the contents; for this reason, it is intended for use in applications where dependency purity isn't very important, such as personal projects, local development scripts, offline data-processing projects, and prototypes.
As a rough sense of scale: a bare `pip install my-basis` pulls a couple dozen distributions (on the order of ~80 MB unpacked); turning on the optional extras (`metrics`, `google`, …) can push a full environment past ~290 MB.

______________________________________________________________________

## See it in action

Two everyday chores, rewritten in front of you.
Each clip is real `my` code: the fragile, hand-rolled version on the left collapses into the one-liner on the right.

### One cast. Every field.

![Coercing a raw config dict into a fully-typed Settings model with ty.cast](assets/vinegif/cast.gif)

`ty.cast` reads the _target_ type and coerces every field to match — `int`, `tuple`, `bool`, nested models and all.
A whole page of `int(...)` / `.split(",")` / `.lower() == "true"` hand-parsing becomes a single, honest line.

### A document, not a string.

![Parsing markdown into a fence-aware node tree with Markdown.parse](assets/vinegif/markdown.gif)

`Markdown.parse` turns a document into a real, fence-aware tree you can `.walk()` to any depth.
So pulling the sections out of a file stops being a `startswith("## ")` slicing exercise that silently breaks the moment a `##` appears inside a code fence.

______________________________________________________________________

## Install

`my-basis` is published to PyPI, so `pip install my-basis` (or `uv add my-basis`) works today — but it's **pre-1.0 and still moving**, so pin a version if you take it that way.
Within this ecosystem, though, every sibling project consumes it the same way: as an editable local path wired through `uv`, so a change here is felt everywhere immediately, with no release round-trip.

```toml
# pyproject.toml
dependencies = [
  "my-basis",
  # ...
]

[tool.uv.sources]
my-basis = { path = "../libs/basis", editable = true }
```

Adjust the relative `path` to wherever this repo lives on disk from the consuming project, then run `uv sync`.

### Optional extras

Core stays small on purpose; everything heavier hangs off an extra you opt into with `pip install my-basis[<extra>]` (or `uv add my-basis --extra <extra>`):

| Extra      | Unlocks                                                                                                                                                          |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `metrics`  | `MetricUtils` — Logfire/OpenTelemetry logging, metrics counters, and instrumentation helpers.                                                                    |
| `google`   | `GoogleSheet` — read/write Google Sheets as pandas `DataFrame`s, with OAuth2 handled for you.                                                                    |
| `myst`     | MyST markdown syntax (admonitions, directives, ...) in `Markdown.render()`'s formatting pass.                                                                    |
| `terminal` | The `pyratatui`-backed terminal-art demos under `my/scripts/tuitorii/`.                                                                                          |
| `aiohttp`  | A convenience pin so `MetricUtils.setup_fire_logging()` can auto-instrument your app's `aiohttp` client when one's already installed — gates nothing on its own. |

Call a `[metrics]` or `[google]` method without installing its extra and you get an actionable `ImportError` naming the exact extra to add, not a bare traceback.

## Quickstart

The core loop: cast untyped data into a target type, check whether a value already fits one, and introspect a type itself as a `MyType` node.

```python
from my import ty, MyType

# Cast: coerce arbitrary data into a target type, best-effort.
ty.cast('42', int)                              # -> 42
ty.cast(['1', '2', '3'], list[int])             # -> [1, 2, 3]   (every element coerced)
ty.cast({'a': '1', 'b': '2'}, dict[str, int])   # -> {'a': 1, 'b': 2}

# Check: does this value already conform to a type, without coercing it?
ty.check(42, int)      # -> True
ty.check('42', int)    # -> False

# MyType: parse any type expression into an introspectable node.
t = MyType(dict[str, int])
t.main    # -> <class 'dict'>
t.args    # -> (MyType[str], MyType[int])
t.root    # -> dict[str, int]
```

`ty` is the package-wide `Typist` singleton -- `cast`/`check`/`match` chambers composed onto one object.
See `docs/` (built locally with `task docs`, or the hosted site once published) for the full subpackage tour: `typing` (this cast/check/match/`MyType` machinery), `types`, `regex`, `caches`, `apis`, `utils`, and `files`.

## Modules

### Utility Functions

#### Iteration Utilities

#### Syntax Utilities

#### Semantic Utilities

#### Text Utilities

#### Code Utilities

#### System Utilities

##### Logging
##### Profiling
##### Command Line Interaction
##### File System Validation

#### Enumerations

#### UUIDs

#### Environment Variables

### Reusable Types

#### Minskian Predicates

### Type Coercion

#### "Vibe" Typing

### Text Processing

#### Regex "Stores"

#### Text Buffers

#### Markdown Trees

### Typed Caches

#### File Caches

#### Nested Caches

#### Pickle Caches

### Singleton Interfaces

#### GoogleSheets

#### Environment

## Caveats

### Pydantic-first

Although you can of course use this package without using Pydantic yourself, you'll be missing out on a lot of the ergonomic benefits: basically every class is a Pydantic "model", and the logging functionality included in [`my/base/utils.py`](/my/base/utils.py) exclusively supports Pydantic's `Logfire`.

### Built for Python 3.12+

It would be pretty trivial to make this library work with versions as old as 3.11, and I aim to do this when I find the time.
Anything older than that would be quite the reach however, as the typing code uses 3.11 syntax throughout a relatively complex module.

If you're blocked by this, either:

1. Let me know!

2. See if you can just manually extract the code you need from the repo.
   If you're only using one or two modules, it may be relatively trivial to backport the syntax.
