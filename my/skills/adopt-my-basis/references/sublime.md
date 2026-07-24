# Modern Sublime plugin hosts

Sublime plugins have two Python contracts that must be recorded separately:

1. the source and test floor declared by `project.requires-python`;
2. the Python interpreter embedded in the target Sublime Text build.

Do not infer one from the other.

## Select the host deliberately

Read Sublime's current **API Environments** and **Dev Builds** pages before
changing `.python-version`. In the current development line, Build 4205 replaced
the Python 3.8 host with Python 3.14. A `.python-version` marker of `3.14` selects
that host. The compatibility marker `3.8` selects 3.8 on older builds and is
remapped to 3.14 on new builds. An unknown marker is not a request for a nearby
version; it may fall back to the legacy host.

Therefore a campaign may intentionally use:

```toml
[project]
requires-python = ">=3.13"
```

with:

```text
3.14
```

in `.python-version`. This means "source supports 3.13 and newer; the live
development host under test is 3.14." It does not claim Sublime embeds 3.13.

## Package-Control runtime dependency

An ordinary `pyproject.toml` dependency supports tests and wheels but does not
by itself install a library into Sublime's isolated plugin host. A live package
also needs its Package Control library dependency declared in
`dependencies.json`, with the library resolvable from the configured Package
Control repository.

For my-basis adoption, verify all three surfaces:

- `pyproject.toml` directly declares `my-basis`;
- `dependencies.json` directly declares the `my-basis` Package Control library;
- the repository/channel metadata exposes a compatible `my-basis` wheel and
  each of its runtime dependencies for the selected host.

Do not vendor an untracked copy merely to make the import pass. If a temporary
source checkout is used for live proof, label it as test scaffolding.

## Structural seam

Many related plugins import a shared `myBasis` Sublime package. Treat that
package as the adapter between the editor API and canonical `my-basis`, not as a
second general-purpose utility library.

Prefer this ownership:

```text
my-basis (`my`)
  owns generic text, iterable, typing, filesystem, and RegexStore structures

myBasis
  owns Sublime API adapters, mocks, plugin base classes, package paths, panels,
  prompts, and editor-specific lifecycle behavior

leaf plugin
  owns only its domain behavior
```

Replace copied generic helpers in `myBasis` first. Leaf plugins can then migrate
from local helpers to the adapter or directly to `my` without preserving a third
copy.

## Verification ladder

1. Run the repository's mocked pytest suite on CPython 3.13.
2. Run lint and typing at the declared floor.
3. Run the same suite on CPython 3.14.
4. Load the branch in an isolated portable development build.
5. Record `sublime.version()`, `sys.version`, package import success, and a
   behavior probe through the real plugin host.

If the live build is unavailable, steps 1–3 remain useful but the live-host
result is `unavailable`, not passed.
