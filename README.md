![logo](/assets/logo_512.png)

# `myBasis`: _Ergonomic Python Utilities_
![Pipeline Status](https://img.shields.io/gitlab/pipeline-status/libs/basis?branch=main)
![Test Coverage](https://img.shields.io/gitlab/pipeline-coverage/libs/basis?job_name=test&branch=main)
[![License](https://img.shields.io/gitlab/license/libs/basis)](/LICENSE)
<!-- Not live yet -- restore once the package is published to ReadTheDocs/PyPI:
[![Documentation](https://app.readthedocs.org/projects/my-basis/badge)](https://my-basis.readthedocs.io)
![Python Version](https://img.shields.io/pypi/pyversions/my-basis)
[![PyPI Wheel](https://img.shields.io/pypi/wheel/my-basis)](https://pypi.org/project/my-basis)
[![PyPI Types](https://img.shields.io/pypi/types/my-basis)](https://pypi.org/project/my-basis)
-->

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![pyrefly](https://img.shields.io/endpoint?url=https://pyrefly.org/badge.json)](https://github.com/facebook/pyrefly)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[![img](https://img.shields.io/badge/Sublime%20Text-4200+-aa673a?logo=sublimetext&logoColor=white&labelColor=d18140)](https://www.sublimetext.com/download)

{align="center"}
> An extensive utility library for python, focusing especially on iterables and a Regex "Store".

---

## Install

> `my-basis` is not yet published to PyPI. Every consumer in this ecosystem depends on it the
> same way: as an editable local path added via `uv`.

```toml
# pyproject.toml
dependencies = [
  "my-basis",
  # ...
]

[tool.uv.sources]
my-basis = { path = "../libs/basis", editable = true }
```

> Adjust the relative `path` to wherever this repo lives on disk from the consuming project,
> then run `uv sync`.

## Quickstart

> The core loop: cast untyped data into a target type, check whether a value already fits one,
> and introspect a type itself as a `MyType` node.

```python
from my import ty, MyType

# Cast: coerce arbitrary data into a target type, best-effort.
ty.cast('42', int)                              # -> 42
ty.cast('a,b,c', list[str])                     # -> ['a', 'b', 'c']
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

> `ty` is the package-wide `Typist` singleton -- `cast`/`check`/`match` chambers composed onto
> one object. See `docs/` (built locally with `task docs`, or the hosted site once published)
> for the full subpackage tour: `typing` (this cast/check/match/`MyType` machinery), `types`,
> `regex`, `caches`, `apis`, `utils`, and `files`.
