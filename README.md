# `mySublimeBasis`

> **Status:** Pre-launch — under active development. APIs may change before 1.0.

Typed infrastructure for Sublime Text 4 plugin development.

ST4 ships a Python 3.8 runtime with an untyped, stringly-keyed API: commands receive
`**kwargs` without a schema, test modules fail to import outside a live process, and
event listeners can't declare what they expect.
`mySublimeBasis` addresses all three directly.

______________________________________________________________________

## Plugin base classes

Six families, each a thin generic wrapper around the corresponding `sublime_plugin` base
class.
All inherit from **`MyBase[I]`** where `I` is a [`CommandArguments`](#types) subclass
that declares the command's typed input schema.

| Class                  | Wraps                | Use when                              |
| ---------------------- | -------------------- | ------------------------------------- |
| `_MyViewCommand[I]`    | `TextCommand`        | operating on a single view's content  |
| `_MyWindowCommand[I]`  | `WindowCommand`      | managing multiple views or the window |
| `_MyAppCommand[I]`     | `ApplicationCommand` | global, view-independent commands     |
| `_MyAppListener[I]`    | `EventListener`      | responding to application-wide events |
| `_MyBufferListener[I]` | `TextChangeListener` | reacting to text changes in a buffer  |
| `_MyViewListener[I]`   | `ViewEventListener`  | reacting to events scoped to a view   |

Async variants of all six live under `plugins/aio/`.

The **`Meta`** metaclass *autobinds* each method whose name matches a Sublime
base-class callback (e.g. `on_activated`, `on_modified`), plus any user-defined method
whose leading parameter (after `self`) is named exactly `view`, `edit`, or `window` —
those arguments are satisfied from `self` at call time, so handlers no longer need to
declare them explicitly. A `buffer`-taking method is only autobound when its *name*
matches a base-class callback; naming a leading parameter `buffer` alone does not
trigger autobind. Autobind can be narrowed to a specific list of method names or
disabled entirely with the `autobind` class keyword.

```python
from myBasis import _MyViewCommand, CommandArguments

class OpenArgs(CommandArguments):
    path: str
    readonly: bool = False

class OpenFileCommand(_MyViewCommand[OpenArgs]):
    def run(self):
        view = self.window.open_file(self.args.path)
        if self.args.readonly:
            view.set_read_only(True)
```

## Mock layer

`myBasis.infra.mock` installs stub implementations of `sublime`, `sublime_plugin`, and
`sublime_api` into `sys.modules` when the package is first imported outside a live ST
process.
**`IS_LIVE`** is the canonical flag — `True` only when the real `sublime` module was
already present in `sys.modules` at import time.

The mock layer is what allows plugin modules to import cleanly in any Python environment,
making unit tests, CLI tooling, and type-checking all work without a running editor:

```python
from myBasis import IS_LIVE          # False outside ST
from myPlugin import OpenFileCommand  # imports fine; stubs are in sys.modules
```

External scripts that need stubs before importing anything else should call
`myBasis.infra.mock.install()` explicitly.

## Infrastructure

- **`PATHS`** (`PathRegistry`) — Pydantic model mapping short names (`pkgs`, `user`,
  `base`, `venv`, …) to resolved `Path` objects.
  The module-level singleton is the canonical way to reference ST filesystem locations
  throughout a plugin.

- **`Multiplex`** — Singleton stdout/stderr fan-out that sits between the plugin and
  the real stdout.
  Streams are registered with a mode: `PASSIVE` mirrors output, `WRAPPER` intercepts
  and forwards, `CONSUME` intercepts and suppresses.
  This lets plugin output be routed simultaneously to the ST console, a log file,
  and/or an output panel.

- **`ViewProperties`** / **`@view_property`** — Cache-invalidation layer for computed
  properties on view-based plugin classes.
  A decorated property is re-evaluated only when the view's change count or a hash of
  source content has changed since the last call.

- **`ut`** (`Utils`) — Catch-all for shared helpers: regex compilation, logging, file
  I/O, subprocess wrappers, and more.

## Types

- **`CommandArguments`** — Pydantic `BaseModel` for typed command argument schemas.
  Attach a `StaticPrompt` or `DynamicPrompt` as the class variable `PROMPT` to get an
  auto-generated `input_handlers()` chain for the command palette.

- **`StaticPrompt` / `DynamicPrompt`** — Declarative specs that produce
  `CommandInputHandler` chains (`TextInputHandler` / `ListInputHandler`).

- **`OutputPanel`** — `sublime.View` wrapper for output panels, with helpers for
  writing, clearing, and toggling visibility.

- **`Comment`** — Utilities for working with comment token positions and ranges in a
  source view.

- **`Venv`** — Virtual-environment introspection and management helpers.

## Installation

### As an ST package

Clone into your ST `Packages/` directory so the runtime loads it:

```bash
git clone https://gitlab.com/doering-ai/sublime/basis \
    ~/.config/sublime-text/Packages/mySublimeBasis
```

### As a Python dependency

Add it to your project for testing, tooling, and type checking:

```bash
uv add "sublime-basis @ git+https://gitlab.com/doering-ai/sublime/basis"
```

The mock layer activates automatically on first import, so plugin modules can be
imported and tested in any Python environment without additional setup.

## Development

```bash
task sync          # Install dependencies (uv sync --all-extras)
task lint          # ruff check .
task format        # ruff format .
task typecheck     # ty check
task test          # Run tests inside a live ST instance via st_pytest
task build         # Build wheel
```

Tests are run inside a live ST instance via [`sublime-test`](https://gitlab.com/doering-ai/sublime/pytest) — `mySublimeBasis`'s companion testing toolkit.
See the `sublime-test` README for test-writing patterns and CI configuration.
