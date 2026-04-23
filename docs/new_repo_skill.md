# `myImports` Developer Guide

`myImports` is a Sublime Text 4 plugin that records `import X as Y` statements seen across Python files and provides a completion: typing `..Y` at the start of a line and pressing Tab inserts the full `import X as Y` statement.

---

## Quick-Start: How These Plugin Repos Are Built

This section is the authoritative guide for creating a new repo in the `doering-ai/sublime` group style.

### 1. Required Files

```
myFoo/
├── __init__.py                  # entry point: just `from .myFoo import *  # noqa: F403`
├── pyproject.toml
├── Taskfile.yaml
├── dependencies.json
├── Default.sublime-commands     # command palette registrations
├── Default.sublime-keymap       # optional keybindings
├── myFoo/
│   ├── __init__.py              # re-exports all public symbols
│   └── MyClass.py               # implementation
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_MyClass.py
```

### 2. pyproject.toml Skeleton

Key invariants:
- `requires-python = "==3.8.*"` — non-negotiable; Sublime Text 4 embeds Python 3.8
- `[tool.uv.sources]` wires local sibling repos/wheels instead of PyPI for ST deps

```toml
[project]
name = "sublime-foo"
version = "0.1.0"
description = "..."
requires-python = "==3.8.*"

dependencies = [
  "regex>=2024.11.6",
  "sublime-lib",
  "sublime-basis",
  # "sublime-aio",   # add if using async listeners
]

[dependency-groups]
dev = [
  "better-exceptions>=0.3.3",
  { include-group = "lint" },
  { include-group = "test" },
  { include-group = "typing" },
]
typing = [
  "sublime-stubs",
  "types-regex>=2024.11.6.20241221",
  "typing-extensions>=4.13.2",
  "annotated-types>=0.7.0",
  "eval-type-backport>=0.3.1",
]
lint = ["ruff>=0.14.14"]
test = ["sublime-pytest", "pytest>=8.3.5", "coverage>=7.6.1"]

[build-system]
requires = ["setuptools>=70.0.0", "setuptools-scm>=7", "wheel>=0.40.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.package-dir]
myFoo = 'myFoo'

[tool.uv.sources]
sublime-lib    = { path = "../.pkgs/sublime_lib-2.1.0-py3-none-any.whl" }
sublime-stubs  = { path = "../.pkgs/sublime-stubs" }
sublime-pytest = { path = "../pytest", editable = true }
sublime-basis  = { path = "../basis", editable = true }
# sublime-aio  = { path = "../.pkgs/sublime_aio-0.1.6-py3-none-any.whl" }

[tool.ruff]
target-version = "py38"
extend = '~/.config/ruff/pyproject.toml'
exclude = ['.venv', 'venv', 'dist', '__pycache__']

[tool.ruff.lint]
ignore = ['UP', 'TC001', 'TC002', 'TC003', 'PT']

[tool.pyright]
strictDictionaryInference = true
strictListInference = true
strictSetInference = true
reportDeprecated        = "warning"
reportImportCycles      = "warning"
reportMissingModuleSource  = false
reportMissingTypeArgument  = false
reportUnknownMemberType    = false
reportUnreachable          = false
reportUnusedVariable       = false

[tool.pytest.ini_options]
filterwarnings = ['ignore:assertions not in:pytest.PytestConfigWarning']
```

### 3. Taskfile.yaml Skeleton

`task test` uses `st_pytest` — the `st_pytest` runner from `../pytest` runs tests *inside* the live ST process and proxies output back to the terminal.

```yaml
# yaml-language-server: $schema=https://taskfile.dev/schema.json
version: '3'
tasks:
  sync:      { cmd: "uv sync --all-extras {{.CLI_ARGS}}" }
  build:     { cmd: "uv build --format wheel {{.CLI_ARGS}}" }

  test:      { cmd: "uv run st_pytest --package myFoo {{.CLI_ARGS}}" }
  test:dev:  "uv run st_pytest --package myFoo --sw -vv --no-cov {{.CLI_ARGS}}"
  test:pdb:  "uv run st_pytest --package myFoo -s --pdb --sw -vv --no-cov {{.CLI_ARGS}}"
  test:cov:  "uv run st_pytest --package myFoo --cov=my --cov-report=term-missing {{.CLI_ARGS}}"

  lint:      { cmd: "uv run ruff check . {{.CLI_ARGS}}" }
  format:    { cmd: "uv run ruff format . {{.CLI_ARGS}}" }
  typecheck: { cmd: "uv run pyright {{.CLI_ARGS}}" }
```

### 4. File Layout Convention

Every `.py` file uses exactly these section markers:

```python
############
### HEAD ###
############
### STANDARD
from __future__ import annotations   # always first — required for 3.8 forward refs
from typing import ClassVar, Any
from typing_extensions import TypeAlias

### EXTERNAL
import regex as re                   # use `regex` not stdlib `re`

### INTERNAL
from myBasis import _MyCommand, CommandArguments, ut

############
### DATA ###
############
# module-level TypeAlias, constants, module-scoped singletons

############
### BODY ###
############
class MyClass:
    ...
```

Within classes, use inline section banners:

```python
class MyFoo:
    # `.` Initial / dunder
    # `-` Private
    # `+` Primary
    # `*` Public (classmethods / staticmethods)
    # `x` Properties
```

### 5. myBasis API

`myBasis` is the foundational library; import from it directly. Key exports:

| Symbol | What it is |
|---|---|
| `_MyCommand[I]` | `TextCommand` base — provides `self.view`, `self.edit`, `self.window`, `self.syntax`, `self.row`, `self.col`, `self.has_view()` |
| `_MyWindowCommand[I]` | `WindowCommand` base — provides `self.window` |
| `_MyAppCommand[I]` | `ApplicationCommand` base |
| `_MyBufferListener[I]` | `TextChangeListener` base |
| `_MyAsyncBufferListener[I]` | Async `TextChangeListener` (requires `sublime-aio`) |
| `_MyViewListener[I]` | `ViewEventListener` base |
| `_MyAppListener[I]` | `EventListener` base |
| `CommandArguments` | Pydantic `BaseModel` for typed command args; attach `PROMPT: ClassVar[StaticPrompt]` for auto-generated input handlers |
| `StaticPrompt` / `DynamicPrompt` | Declarative specs that produce `CommandInputHandler` chains |
| `view_property` | Like `@cached_property` but invalidates when the view's change count changes |
| `Comment` | Utilities for working with line-comment token positions in a view |
| `ut` | Catch-all utils: `ut.from_file(glob)`, `ut.clean_rgx_match(m)`, `ut.multiprint(...)` |
| `PATHS` | `PathRegistry` singleton — `PATHS.pkgs`, `PATHS.user`, `PATHS.base`, `PATHS.venv`, … |
| `IS_LIVE` | `True` only inside a real ST process; use for conditional mock/live behaviour |

**Autobind** — `Meta` inspects every ST-style method at class-creation time; if a method accepts `view`, `edit`, `buffer`, or `window`, those are satisfied automatically from the instance. You get `self.view` etc. throughout the class without threading them manually.

### 6. Plugin Families

**TextCommand** (`_MyCommand[I]`): instantiated once per view; `run(self, edit, **kwargs)` is the entry point. `is_enabled(**_)` and `is_visible(**_)` are optional guards.

```python
class MyArgs(CommandArguments):
    alias: str = ''

class MyCommand(_MyCommand[MyArgs]):
    def run(self, edit, alias: str = '') -> None:
        args = MyArgs(alias=alias)
        self.view.insert(edit, self.view.sel()[0].begin(), f'import foo as {args.alias}\n')
```

**Listener** (`_MyAsyncBufferListener[I]`): runs automatically on buffer events. Use `sublime_aio.debounced(ms)` to rate-limit `on_modified`:

```python
import sublime_aio as sbaio
from myBasis import _MyAsyncBufferListener

class MyListener(_MyAsyncBufferListener):
    @sbaio.debounced(500)
    async def on_modified(self):
        self._handle_change()
```

### 7. CommandArguments + Input Handlers

```python
class MyArgs(CommandArguments):
    alias: str
    PROMPT: ClassVar = StaticPrompt(fields=['alias'], placeholder='alias name')

class MyCommand(_MyCommand[MyArgs]):
    def input_handlers(self): return MyArgs.PROMPT.build(self)
    def run(self, edit, alias: str) -> None: ...
```

### 8. Sublime Text Boilerplate

**`__init__.py`** (package root — the file ST loads):

```python
from .myFoo import *  # noqa: F403
```

**`myFoo/__init__.py`**:

```python
from .MyClass import MyClass, MyCommand
__all__ = ['MyClass', 'MyCommand']
```

**`Default.sublime-commands`**:

```json
[{"caption": "My: Do Thing", "command": "my_command"}]
```

**`dependencies.json`** (PackageControl dependencies — usually just these):

```json
{
    "$schema": "sublime://packagecontrol.io/schemas/dependencies",
    "*": { ">=4096": ["typing-extensions", "annotated-types", "eval_type_backport"] }
}
```

### 9. Testing

```python
############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, Any

### EXTERNAL
import pytest as pyt

### INTERNAL
from myFoo import MyClass

cls = MyClass


############
### BODY ###
############
class TestMyClass:
    @pyt.mark.parametrize('input, expected', [
        ('np', 'import numpy as np'),
        ('pd', 'import pandas as pd'),
    ])
    def test_lookup(self, input: str, expected: str):
        assert cls.lookup(input) == expected
```

Conventions:
- `import pytest as pyt` (not bare `pytest`)
- Short alias at module level (`cls = ClassName`) for the class under test
- No `### DATA ###` unless there's substantial fixture data
- For ST command tests, inherit `MyCommandTestSuite[MyCommand]` from `PyTest`
- Register type coercers in `conftest.py` via `register_param_handler`

Run tests:

```bash
task test                                       # all tests
task test -- tests/test_MyClass.py              # one file
task test:dev                                   # with -vv --sw, no coverage
```

---

## myImports Architecture

### Responsibility Split

| Component | Class | Mechanism |
|---|---|---|
| **Recorder** | `ImportAsListener` | `_MyAsyncBufferListener`; on buffer save, scans for `import X as Y` lines and upserts them into the alias store |
| **Store** | `ImportStore` | Plain Pydantic model wrapping a JSON file in `PATHS.user / 'myImports.json'`; maps `alias → full_statement` |
| **Completion** | `ImportAsCompletion` | ST `EventListener` (`on_query_completions`); when the cursor is at BOL in a Python file, returns completions for all `..alias` prefixes |

### Alias File

`~/.config/sublime-text/User/myImports.json`:

```json
{"np": "import numpy as np", "pd": "import pandas as pd"}
```

`PATHS.user` resolves to `~/.config/sublime-text/User/` via `myBasis.PATHS`.

### Completion Trigger

The `..alias` prefix with Tab at start-of-line is implemented via `on_query_completions`:

- Check scope is Python and cursor is at column 0 (or the only content before cursor is `..`)
- Strip the leading `..` to get the alias prefix
- Return matching `import X as Y\n` completions with `sublime.INHIBIT_WORD_COMPLETIONS`

### Data Flow

```
User types `import numpy as np`
  → on_modified (debounced 500ms)
    → scan buffer for `^import \S+ as (\w+)$`
      → upsert {"np": "import numpy as np"} into store

User types `..np` at BOL, presses Tab
  → on_query_completions
    → prefix strip → lookup "np" → return "import numpy as np\n"
      → ST inserts the full import and removes the `..np` trigger
```
