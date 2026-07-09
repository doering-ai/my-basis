# PyRatatui 4D Torus Showcase

This directory contains a small terminal-art showcase for `myBasis`: a rotating
4D Clifford torus rendered from Python through [`pyratatui`][pyratatui], the
Python binding for Ratatui.

The demo follows the Ratatui animation pattern recommended by the upstream
project and codified in the `building-ratatui` corpus skill:

- keep animation state in an application object;
- draw complete frames through Ratatui/PyRatatui and let the buffer diffing
  layer update the terminal;
- drive motion from elapsed time instead of treating each frame as one fixed
  simulation step;
- use `Terminal()` as a context manager so alternate-screen/raw-mode setup is
  restored on exit;
- keep input handling centralized and non-blocking.

## Run

Install the optional terminal dependency, then run the module:

```zsh
uv run --extra terminal python my/scripts/tuitorii/torus.py
```

The module form below should also work once the top-level `my` package imports
cleanly in the current checkout:

```zsh
uv run --extra terminal python -m my.scripts.tuitorii
```

Controls:

| Key         | Effect                      |
| ----------- | --------------------------- |
| `q` / `Esc` | quit                        |
| `Space`     | pause/resume                |
| `+` / `=`   | increase rotation speed     |
| `-` / `_`   | decrease rotation speed     |
| `r`         | reset speed and pause state |

For a non-interactive geometry smoke test, render one ASCII snapshot:

```zsh
uv run --extra terminal python my/scripts/tuitorii/torus.py --snapshot
```

## Tests

The pure-geometry core (rotation, projection, clock/pause/reset logic, config
bounds, and the deterministic snapshot shape) is covered by
`tests/scripts/test_torus.py`. PyRatatui is imported lazily, so the geometry
tests run without the `terminal` extra; only the draw-path tests use
`importorskip('pyratatui')`.

```zsh
uv run pytest tests/scripts/test_torus.py -v
```

## Why a Clifford torus?

The point cloud is sampled from the 4D product of two circles:

```text
(x, y, z, w) = (cos u, sin u, cos v, sin v)
```

Each frame rotates the sampled surface in several 4D coordinate planes, then
projects 4D -> 3D -> 2D. Nearer projected points are drawn after farther ones so
the terminal image has a simple depth cue.

## See also

- The `building-ratatui` corpus skill, which codifies Ratatui/PyRatatui TUI
  conventions (application-object state, elapsed-time motion, context-managed
  `Terminal()`).

[pyratatui]: https://github.com/pyratatui/pyratatui
