# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`mySublimeBasis` is a shared library for developing SublimeText 4 plugins.
It provides typed base classes, infrastructure utilities, and mock modules so that plugin code can be imported and used outside the live SublimeText runtime.

## Development

### Important tools

**Python 3.8** is used throughout the project, as this is the version embedded in Sublime Text 4's plugin environment.
In general more modern development practices are used wherever possible (type annotations, `pyproject.toml`, etc.).

**`uv`** serves as the package manager and build system, putting downloaded dependencies into the **`.venv/`** directory.
We use Astro's linter and formatter **`ruff`**, and Astro's type checker **`ty`**.

Local Sublime Text dependencies (`sublime-stubs`, `sublime-lib`, `sublime-aio`) are resolved via `uv.sources` pointing to sibling directories and wheels under `../_*`.

**`Taskfile.yaml`** (a symlink to a shared `../_Taskfile.yaml`) wraps the common commands:

```bash
task sync          # Install dependencies
task build         # Build wheel
task lint          # ruff check .
task format        # ruff format .
task typecheck     # ty check (or pyright)
task test          # Run tests via st_pytest inside a Sublime Text instance
task test:dev      # Same, with -vv --sw --no-cov
```

Tests are written with **`pytest`** and live in **`tests/`**.  They are run inside SublimeText via the `st_pytest` wrapper from the sibling `PyTest` package, which injects the mock `sublime` / `sublime_plugin` modules so tests can also run from the CLI without a live ST process.

### Sublime Text directories

You can find Sublime Text packages at `$ST_PKGS` and the core API & executable at `$ST_ROOT`.

## Code Architecture

### Mock layer (`infra/mock/`)

Stub implementations of `sublime`, `sublime_plugin`, and `sublime_api` that are automatically injected into `sys.modules` when the package is imported outside a live ST process.
The module-level boolean **`IS_LIVE`** is the canonical flag for whether the real ST runtime is active — it is `True` only when the real `sublime` module is already in `sys.modules` at import time.
External scripts should call `myBasis.infra.mock.install()` explicitly if they need the stubs before importing anything else.

### Infrastructure (`infra/`)

- **`PathRegistry`** (`PathRegistry.py`) — Pydantic model mapping short names (`pkgs`, `user`, `base`, `venv`, …) to resolved `Path` objects. The module-level singleton **`PATHS`** is the primary way to reference ST filesystem locations throughout a plugin.

- **`Multiplex`** (`Multiplex.py`) — Singleton stdout/stderr fan-out that sits between the plugin and the real stdout. Streams are registered with a mode: `PASSIVE` mirrors output, `WRAPPER` intercepts and forwards, `CONSUME` intercepts and suppresses. This lets plugin output be routed simultaneously to the ST console, a log file, and/or an output panel.

- **`ViewProperties`** (`ViewProperties.py`) — Cache-invalidation layer for computed properties on view-based plugin classes. A property decorated with **`@view_property`** is re-evaluated only when the view's change count or a hash of source content has changed since the last call.

- **`utils.py`** — The `Utils` class, exported as **`ut`** and **`utils`**. Catch-all for shared helpers: regex compilation, logging, file I/O, subprocess wrappers, and more.

- **`constants.py`** — `EVENTS` (a dict of ST event names grouped by scope) and `ASYNCABLE_EVENTS` (the subset that are safe to make async).

### Plugin base classes (`plugins/`)

All plugin classes go through the **`Meta`** metaclass defined in `_MyBase.py`.
`Meta` inspects each ST-style method on a subclass at class-creation time: if a method accepts a `view`, `buffer`, `window`, or `edit` argument, it is wrapped so that argument is satisfied automatically from the instance (autobind).
The stored values are then accessible as `self.view`, `self.window`, `self.buffer`, and `self.edit` throughout the class.
Autobind can be limited to a specific list of method names or disabled entirely with the `autobind` class keyword.

Six plugin families are provided, each inheriting from `MyBase[I]` where `I` is a `CommandArguments` subclass:
`_MyCommand` (TextCommand), `_MyWindowCommand` (WindowCommand), `_MyAppCommand` (ApplicationCommand), `_MyAppListener` (EventListener), `_MyBufferListener` (TextChangeListener), and `_MyViewListener` (ViewEventListener).
Async variants of all six live under `plugins/aio/`.

### Types (`types/`)

- **`CommandArguments`** — Pydantic `BaseModel` that defines a command's typed argument schema. Attach a `StaticPrompt` or `DynamicPrompt` instance as the class variable `PROMPT` to get an auto-generated `input_handlers()` chain.
- **`StaticPrompt` / `DynamicPrompt`** — Declarative specs that produce ST `CommandInputHandler` chains (`TextInputHandler` / `ListInputHandler`).
- **`OutputPanel`** — Wrapper around `sublime.View` for output panels, with helpers for writing, clearing, and toggling visibility.
- **`Comment`** — Utilities for working with comment token positions and ranges in a source view.
- **`Venv`** — Virtual-environment introspection and management helpers.

## Common Development Patterns

- Section markers inside files: `### HEAD ###` (imports), `### DATA ###` (module-level constants/types), `### BODY ###` (implementation).
- Method organization within classes: `.` initial/dunder, `-` private, `+` primary, `*` public (classmethod/staticmethod), `x` property.
- Import grouping: Standard → External → Internal.
- `from __future__ import annotations` is in every file (required for Python 3.8 forward-reference support).
- The third-party `regex` package is used instead of stdlib `re`; `re.DEFAULT_VERSION = re.VERSION1` is set globally in `utils.py`.
